"""Nota de crédito: corregir una venta que ya se cobró (RN-CPP-009).

Anular no es borrar. Una vez que SUNAT aceptó el comprobante, la venta solo
se corrige emitiendo un documento nuevo que la acredita —total o por ítem—
con un motivo del catálogo 09. Por eso `anular_venta` sigue cubriendo solo
la orden sin cobrar y manda acá el resto.

Tres cosas las decide quien emite, porque el ERP no puede adivinarlas:

- **Qué se acredita**: sin detalle va entera; con detalle, solo esas líneas
  y esas cantidades, validadas contra lo que quedaba por acreditar.
- **Si el stock vuelve**: `repone_stock` es explícito. Un plato devuelto en
  cocina rara vez devuelve el insumo, y corregir el RUC de una factura no
  toca el inventario en absoluto.
- **Por qué**: el motivo decide además si la venta queda anulada
  (anulación/devolución) o sigue viva para reemitir el comprobante
  corregido (error de RUC o de descripción).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.sales.application import comprobantes
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.repositories import (
    ComprobanteRepo,
    ProductoComercialRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.shared.integrations import factiliza
from src.shared.models import Comprobante


def _serie_nc(punto_venta, tipo: str) -> str:
    """Serie propia del documento de crédito.

    Sin ella no se emite: SUNAT rechaza la nota que numera en la serie de la
    boleta o factura, y es mejor decirlo antes que quemar un correlativo.
    """
    serie = (
        punto_venta.serie_nc_factura
        if tipo == "factura"
        else punto_venta.serie_nc_boleta
    )
    if not serie:
        raise Conflicto(
            f"el punto de venta no tiene serie de nota de crédito para {tipo}: "
            "configúrala antes de acreditar"
        )
    return serie


def _acreditado_previo(session: Session, comprobante_id: uuid.UUID) -> dict[str, Decimal]:
    """Cuánto de cada línea ya acreditaron notas anteriores.

    Solo cuentan las aceptadas: una NC rechazada por SUNAT no devolvió nada,
    y bloquear con ella dejaría la venta sin forma de corregirse.
    """
    acumulado: dict[str, Decimal] = {}
    for nota in ComprobanteRepo(session).notas_de_credito_de(comprobante_id):
        if nota.estado_emision != "aceptado":
            continue
        for linea in nota.detalle_nc or []:
            clave = str(linea["venta_item_id"])
            acumulado[clave] = acumulado.get(clave, Decimal(0)) + Decimal(
                str(linea["cantidad"])
            )
    return acumulado


def _lineas_acreditadas(
    session: Session, afectado: Comprobante, detalle: list[dict] | None
) -> tuple[list, dict[str, Decimal]]:
    """Líneas de la venta que esta nota acredita, con su cantidad.

    `detalle` en `None` = nota total: todo lo que el comprobante documenta,
    con las cantidades vendidas.
    """
    filas = VentaRepo(session).items(
        afectado.venta_id, grupo_cobro=afectado.grupo_cobro
    )
    vendidas = {str(f.id): f.cantidad for f in filas}
    if detalle is None:
        return filas, vendidas

    devueltas = {
        str(linea["venta_item_id"]): Decimal(str(linea["cantidad"]))
        for linea in detalle
    }
    problemas = rules.cantidades_acreditables(
        devueltas, vendidas, _acreditado_previo(session, afectado.id)
    )
    if problemas:
        raise ReglaNegocio("; ".join(problemas))
    return [f for f in filas if str(f.id) in devueltas], devueltas


def _items_para_reponer(session: Session, filas, cantidades: dict[str, Decimal]) -> list[dict]:
    """Payload de reposición con el mismo shape que `sales.venta_anulada`,
    para que lo consuma el listener de inventory que ya existe."""
    productos = ProductoComercialRepo(session)
    items = []
    for fila in filas:
        prod = productos.get(fila.producto_comercial_id)
        if prod is None or prod.receta_id is None:
            continue
        items.append(
            {"receta_id": str(prod.receta_id), "cantidad": str(cantidades[str(fila.id)])}
        )
    return items


def _documento_de_nota(
    session: Session,
    nota: Comprobante,
    afectado: Comprobante,
    filas,
    cantidades: dict[str, Decimal],
) -> factiliza.Documento:
    """Reusa el armado del comprobante afectado y le cambia las cantidades.

    Los precios, el descuento prorrateado y el régimen de IGV tienen que ser
    exactamente los del documento que se corrige: recalcularlos por separado
    sería la forma segura de que la nota no cuadre contra su original.
    """
    base = comprobantes.documento_de(session, afectado)
    precios = {i.codigo: i.precio_unitario for i in base.items}
    productos = ProductoComercialRepo(session)
    items = []
    for fila in filas:
        prod = productos.get(fila.producto_comercial_id)
        codigo = str(prod.id) if prod else str(fila.producto_comercial_id)
        items.append(
            factiliza.Item(
                codigo=codigo,
                descripcion=prod.nombre if prod else "PRODUCTO",
                cantidad=cantidades[str(fila.id)],
                precio_unitario=precios.get(codigo, fila.precio_unitario),
            )
        )
    return factiliza.Documento(
        empresa_ruc=base.empresa_ruc,
        tipo_doc=factiliza.TIPO_DOC_NOTA_CREDITO,
        serie=nota.serie,
        correlativo=nota.correlativo,
        fecha_emision=datetime.now(UTC),
        cliente=base.cliente,
        items=items,
        exonerado_igv=base.exonerado_igv,
        igv_porcentaje=base.igv_porcentaje,
    )


def _enviar(
    session: Session,
    nota: Comprobante,
    afectado: Comprobante,
    filas,
    cantidades: dict[str, Decimal],
    client: factiliza.FactilizaClient | None,
) -> None:
    nota.intentos_emision += 1
    payload = factiliza.construir_payload_nota_credito(
        _documento_de_nota(session, nota, afectado, filas, cantidades),
        factiliza.DocumentoAfectado(
            tipo_doc=(
                factiliza.TIPO_DOC_FACTURA
                if afectado.tipo == "factura"
                else factiliza.TIPO_DOC_BOLETA
            ),
            serie=afectado.serie,
            correlativo=afectado.correlativo,
        ),
        nota.motivo_nc,
        nota.motivo_nc_descripcion,
    )
    respuesta = (client or factiliza.FactilizaClient()).enviar_nota_credito(payload)
    nota.respuesta_proveedor = respuesta.crudo
    nota.detalle_emision = respuesta.mensaje[:1000] if respuesta.mensaje else None
    nota.estado_emision = "aceptado" if respuesta.aceptado else "rechazado"
    if respuesta.aceptado:
        nota.hash_proveedor = respuesta.hash


def _aplicar_efectos(
    session: Session,
    nota: Comprobante,
    afectado: Comprobante,
    filas,
    cantidades: dict[str, Decimal],
    *,
    repone_stock: bool,
    emitido_por: uuid.UUID,
) -> None:
    """Lo que la nota cambia fuera del documento.

    Una nota de corrección (error de RUC, error en la descripción) **no
    anula la venta**: la operación ocurrió, el papel estaba mal. Marca el
    comprobante para que pueda reemitirse el corregido y nada más.
    """
    es_total = nota.detalle_nc is None
    de_correccion = nota.motivo_nc in factiliza.MOTIVOS_NC_DE_CORRECCION
    venta = VentaRepo(session).get(nota.venta_id)

    if es_total:
        afectado.anulado_por_nc_id = nota.id
        if venta is not None and not de_correccion:
            venta.estado = "anulada"

    event_bus.publish(
        "sales.nota_credito_emitida",
        {
            "nota_credito_id": str(nota.id),
            "comprobante_id": str(afectado.id),
            "venta_id": str(nota.venta_id),
            "sucursal_id": str(venta.sucursal_id) if venta else None,
            "motivo": nota.motivo_nc,
            "total": es_total,
            "emitido_por": str(emitido_por),
            "repone_stock": repone_stock,
            # Mismo shape que `sales.venta_anulada`: sin reposición viaja
            # vacío y el listener de inventory no mueve nada.
            "items": (
                _items_para_reponer(session, filas, cantidades) if repone_stock else []
            ),
        },
        session=session,
    )


def emitir_nota_credito(
    session: Session,
    comprobante_id: uuid.UUID,
    *,
    motivo: str,
    emitido_por: uuid.UUID,
    detalle: list[dict] | None = None,
    repone_stock: bool = True,
    motivo_descripcion: str | None = None,
    client: factiliza.FactilizaClient | None = None,
) -> Comprobante:
    """Acredita un comprobante ya aceptado por SUNAT.

    `detalle` es `[{"venta_item_id": ..., "cantidad": ...}]`; sin él la nota
    es total. La emisión va **en línea** y no por cola: quien acredita
    necesita el veredicto ahí mismo, igual que al reintentar. Sin token de
    Factiliza configurado la nota queda `pendiente`, como cualquier
    comprobante.
    """
    repo = ComprobanteRepo(session)
    afectado = repo.get(comprobante_id)
    if afectado is None:
        raise NoEncontrado("comprobante no encontrado")
    if motivo not in factiliza.MOTIVOS_NC:
        raise ReglaNegocio(f"motivo fuera del catálogo 09 de SUNAT: {motivo}")
    if not rules.puede_notacreditar(
        afectado.estado_emision, afectado.anulado_por_nc_id is not None
    ):
        ya = " y ya fue anulado por otra nota" if afectado.anulado_por_nc_id else ""
        raise Conflicto(
            f"el comprobante está {afectado.estado_emision}{ya}: solo se acredita "
            "un comprobante aceptado y no acreditado antes"
        )

    filas, cantidades = _lineas_acreditadas(session, afectado, detalle)
    if not filas:
        raise ReglaNegocio("la nota de crédito no acredita ninguna línea")

    punto_venta = PuntoVentaRepo(session).get(afectado.punto_venta_id)
    if punto_venta is None:
        raise NoEncontrado("punto de venta no encontrado")

    serie = _serie_nc(punto_venta, afectado.tipo)
    nota = Comprobante(
        empresa_id=afectado.empresa_id,
        venta_id=afectado.venta_id,
        grupo_cobro=afectado.grupo_cobro,
        punto_venta_id=afectado.punto_venta_id,
        direccion="emitido",
        tipo="nc",
        serie=serie,
        correlativo=repo.siguiente_correlativo(afectado.empresa_id, serie),
        sustento=afectado.sustento,
        # Una misma venta puede necesitar varias notas parciales: la clave
        # cuenta cuántas lleva, así que reintentar la misma no duplica pero
        # una segunda devolución sí es un documento nuevo.
        idempotency_key=f"nc:{afectado.id}:{repo.cuantas_nc(afectado.id) + 1}",
        estado_emision="pendiente",
        receptor_num_doc=afectado.receptor_num_doc,
        receptor_nombre=afectado.receptor_nombre,
        afecta_comprobante_id=afectado.id,
        motivo_nc=motivo,
        motivo_nc_descripcion=motivo_descripcion or factiliza.MOTIVOS_NC[motivo],
        detalle_nc=(
            None
            if detalle is None
            else [
                {"venta_item_id": clave, "cantidad": str(valor)}
                for clave, valor in cantidades.items()
            ]
        ),
    )
    session.add(nota)
    session.flush()

    if comprobantes.emision_habilitada():
        _enviar(session, nota, afectado, filas, cantidades, client)

    # Una nota rechazada por SUNAT no devolvió nada: no repone stock ni anula
    # la venta. Queda registrada con su motivo para corregir y reintentar.
    if nota.estado_emision in ("pendiente", "aceptado"):
        _aplicar_efectos(
            session,
            nota,
            afectado,
            filas,
            cantidades,
            repone_stock=repone_stock,
            emitido_por=emitido_por,
        )
    return nota
