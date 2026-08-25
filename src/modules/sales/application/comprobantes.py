"""Emisión del comprobante electrónico de una venta (boleta / factura).

Dos pasos deliberadamente separados: al cobrar se crea el `comprobante`
en estado `pendiente` (rápido, dentro de la transacción de la venta), y el
envío a Factiliza corre en la cola. Una caída del proveedor deja el
comprobante pendiente de reintento, nunca bloquea la caja (RN-COM-003).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Venta
from src.modules.sales.infrastructure.repositories import (
    ClienteRepo,
    ComprobanteRepo,
    ProductoComercialRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.shared import fechas
from src.shared.integrations import factiliza
from src.shared.models import Comprobante

MAX_INTENTOS_EMISION = 5


def emision_habilitada() -> bool:
    """Sin token configurado no hay facturación electrónica: el ERP sigue
    operando y los comprobantes quedan pendientes."""
    return bool(settings.factiliza_token)


def pendientes_de_emitir(session, limite: int = 100) -> list[uuid.UUID]:
    """Comprobantes que quedaron sin llegar a SUNAT y todavía pueden llegar.

    El reintento por comprobante (backoff de la cola) cubre la caída pasajera
    de Factiliza. Esto cubre lo que la cola nunca supo: el comprobante
    emitido cuando no había `FACTILIZA_TOKEN`, el que nació con el broker
    caído (`retry=False` a propósito, para no colgar la caja), o el que se
    perdió con el worker muerto.
    """
    return [
        c.id
        for c in ComprobanteRepo(session).pendientes(
            limite=limite, max_intentos=MAX_INTENTOS_EMISION
        )
    ]


def clave_idempotencia(venta_id, grupo_cobro: int) -> str:
    """El grupo 1 conserva la clave histórica `venta:{id}`: los comprobantes
    emitidos antes del cobro dividido siguen resolviendo idempotentes."""
    if grupo_cobro == rules.GRUPO_COBRO_UNICO:
        return f"venta:{venta_id}"
    return f"venta:{venta_id}:g{grupo_cobro}"


def crear_comprobante_pendiente(
    session: Session,
    venta: Venta,
    *,
    grupo_cobro: int = rules.GRUPO_COBRO_UNICO,
    receptor_num_doc: str | None = None,
    receptor_nombre: str | None = None,
) -> Comprobante | None:
    """Idempotente por venta y grupo de cobro: cobrar dos veces la misma
    cuenta no duplica el comprobante, pero dos cuentas distintas de la misma
    venta sí emiten dos documentos (RN-COM-018)."""
    repo = ComprobanteRepo(session)
    existente = repo.por_venta_y_grupo(venta.id, grupo_cobro)
    if existente is not None:
        return existente

    punto_venta = PuntoVentaRepo(session).get(venta.punto_venta_id)
    if punto_venta is None:
        raise NoEncontrado("punto de venta no encontrado")
    empresa = repo.empresa_de_sucursal(venta.sucursal_id)
    if empresa is None:
        raise NoEncontrado("empresa de la sucursal no encontrada")

    if receptor_num_doc:
        # El documento tecleado en caja manda: es el que el cliente pidió.
        if not rules.documento_receptor_valido(receptor_num_doc):
            raise ReglaNegocio(
                "el documento del receptor debe tener 8 dígitos (DNI) u 11 (RUC)"
            )
        tipo = rules.tipo_comprobante_por_documento(receptor_num_doc)
    else:
        cliente = (
            ClienteRepo(session).get(venta.cliente_id) if venta.cliente_id else None
        )
        tipo = rules.tipo_comprobante(
            cliente.tipo if cliente else None, cliente.ruc if cliente else None
        )
    serie = punto_venta.serie_factura if tipo == "factura" else punto_venta.serie_boleta

    comprobante = Comprobante(
        empresa_id=empresa.id,
        venta_id=venta.id,
        grupo_cobro=grupo_cobro,
        punto_venta_id=punto_venta.id,
        direccion="emitido",
        tipo=tipo,
        serie=serie,
        correlativo=repo.siguiente_correlativo(empresa.id, serie),
        sustento="voucher_medio_pago",
        idempotency_key=clave_idempotencia(venta.id, grupo_cobro),
        estado_emision="pendiente",
        receptor_num_doc=receptor_num_doc or None,
        receptor_nombre=receptor_nombre or None,
    )
    session.add(comprobante)
    session.flush()
    return comprobante


def fecha_emision(comprobante: Comprobante) -> datetime:
    """La fecha que el documento declara, en hora del negocio.

    Es el instante del cobro (`created_at`) y no "ahora": un comprobante que
    se quedó en la cola —proveedor caído, worker muerto, `FACTILIZA_TOKEN`
    sin configurar— y sale al día siguiente sigue documentando la venta de
    ayer. Con `now()` el barrido de pendientes le ponía al papel una fecha
    que la venta nunca tuvo.

    Y se lee en `America/Lima`: una venta de las 20:00 en Tarapoto es del
    día 25 aunque en UTC ya sea 26. Es la misma trampa que documenta
    `shared.fechas`.

    La base guarda `created_at` con zona, pero SQLite la pierde en el viaje
    de ida y vuelta; un instante sin zona se lee como UTC, que es lo que la
    columna guarda.
    """
    nacido = comprobante.created_at or datetime.now(UTC)
    if nacido.tzinfo is None:
        nacido = nacido.replace(tzinfo=UTC)
    return nacido.astimezone(fechas.zona())


def documento_de(session: Session, comprobante: Comprobante) -> factiliza.Documento:
    """El documento tal como se envió (o se enviaría) a SUNAT.

    Público porque la nota de crédito lo reusa: sus líneas tienen que llevar
    los mismos precios, el mismo descuento prorrateado y el mismo régimen de
    IGV que el comprobante que corrige.
    """
    return _documento(session, comprobante)


def _documento(session: Session, comprobante: Comprobante) -> factiliza.Documento:
    repo = ComprobanteRepo(session)
    empresa = repo.empresa(comprobante.empresa_id)
    venta_repo = VentaRepo(session)
    venta = venta_repo.get(comprobante.venta_id)
    productos = ProductoComercialRepo(session)

    # Solo las líneas de la cuenta que este comprobante documenta.
    filas = venta_repo.items(venta.id, grupo_cobro=comprobante.grupo_cobro)
    subtotales = [f.cantidad * f.precio_unitario - f.descuento for f in filas]
    # El descuento manual de la orden se prorratea entre TODAS sus líneas;
    # a este comprobante le toca la parte de su grupo.
    todos = venta_repo.items(venta.id)
    base_venta = sum(
        (f.cantidad * f.precio_unitario - f.descuento for f in todos), Decimal(0)
    )
    del_grupo = rules.descuento_prorrateado(
        venta.descuento_modo,
        venta.descuento_valor,
        base_venta,
        sum(subtotales, Decimal(0)),
    )
    por_linea = rules.repartir_descuento(del_grupo, subtotales)

    items = []
    for it, extra in zip(filas, por_linea, strict=True):
        prod = productos.get(it.producto_comercial_id)
        # El descuento se reparte en el precio unitario: el endpoint de
        # Factiliza no recibe descuento por línea.
        neto = rules.precio_unitario_neto(
            it.cantidad, it.precio_unitario, it.descuento + extra
        )
        items.append(
            factiliza.Item(
                codigo=str(prod.id) if prod else str(it.producto_comercial_id),
                descripcion=prod.nombre if prod else "PRODUCTO",
                cantidad=it.cantidad,
                precio_unitario=neto,
            )
        )

    return factiliza.Documento(
        empresa_ruc=empresa.ruc,
        tipo_doc=(
            factiliza.TIPO_DOC_FACTURA
            if comprobante.tipo == "factura"
            else factiliza.TIPO_DOC_BOLETA
        ),
        serie=comprobante.serie,
        correlativo=comprobante.correlativo,
        fecha_emision=fecha_emision(comprobante),
        cliente=_receptor_para_sunat(session, comprobante, venta),
        items=items,
        # Ley 27037: las empresas de Amazonía venden exoneradas de IGV
        # (RN-IMP-001). El régimen lo declara la empresa, no la venta.
        exonerado_igv=empresa.zona_tributaria == "amazonia_ley27037",
        igv_porcentaje=settings.igv_porcentaje,
    )


def _receptor_para_sunat(
    session: Session, comprobante: Comprobante, venta: Venta
) -> factiliza.Cliente:
    """El documento tecleado en caja gana sobre el cliente de la venta: es
    el que el cliente pidió en el momento del cobro (RN-CPP-003). Sin él,
    se resuelve como siempre desde `venta.cliente_id`.
    """
    if comprobante.receptor_num_doc:
        num = comprobante.receptor_num_doc
        es_ruc = len(num) == rules.LARGO_RUC
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_RUC if es_ruc else rules.DOC_SUNAT_DNI,
            num_doc=num,
            razon_social=comprobante.receptor_nombre or "CLIENTES VARIOS",
            direccion="-",
        )
    cliente = ClienteRepo(session).get(venta.cliente_id) if venta.cliente_id else None
    return _cliente_para_sunat(session, cliente)


def _cliente_para_sunat(session: Session, cliente) -> factiliza.Cliente:
    """Cliente anónimo es válido en boleta (RN-PER-005)."""
    if cliente is None:
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_SIN_DOCUMENTO,
            num_doc="00000000",
            razon_social="CLIENTES VARIOS",
        )
    if cliente.tipo == "juridico":
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_RUC,
            num_doc=cliente.ruc or "",
            razon_social=cliente.razon_social or "",
            direccion=cliente.contacto or "-",
        )
    persona = ComprobanteRepo(session).persona(cliente.persona_id)
    if persona is None:
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_SIN_DOCUMENTO,
            num_doc=rules.SIN_DOCUMENTO,
            razon_social="CLIENTES VARIOS",
        )
    # Un cliente registrado solo por teléfono no tiene documento: la boleta
    # sale igual, a su nombre, con el documento genérico (RN-PER-005).
    if not rules.cliente_identificado(persona.numero_documento):
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_SIN_DOCUMENTO,
            num_doc=rules.SIN_DOCUMENTO,
            razon_social=f"{persona.nombres} {persona.apellidos}".strip()
            or "CLIENTES VARIOS",
            direccion=persona.domicilio or "-",
        )
    return factiliza.Cliente(
        tipo_doc=rules.doc_sunat_de_persona(persona.tipo_documento),
        num_doc=persona.numero_documento,
        razon_social=f"{persona.nombres} {persona.apellidos}".strip(),
        direccion=persona.domicilio or "-",
    )


def emitir_comprobante(
    session: Session,
    comprobante_id: uuid.UUID,
    client: factiliza.FactilizaClient | None = None,
) -> Comprobante:
    """Envía a Factiliza y persiste el veredicto de SUNAT.

    Levanta `FactilizaError` ante fallo de transporte para que la cola
    reintente; un rechazo de SUNAT no es excepción, es un veredicto.
    """
    comprobante = ComprobanteRepo(session).get(comprobante_id)
    if comprobante is None:
        raise NoEncontrado("comprobante no encontrado")
    if comprobante.estado_emision == "aceptado":
        return comprobante
    if comprobante.direccion != "emitido":
        raise Conflicto("solo se emite un comprobante propio, no uno recibido")
    if comprobante.intentos_emision >= MAX_INTENTOS_EMISION:
        raise Conflicto(
            f"comprobante agotó {MAX_INTENTOS_EMISION} intentos; requiere revisión manual"
        )

    comprobante.intentos_emision += 1
    payload = factiliza.construir_payload(_documento(session, comprobante))
    respuesta = (client or factiliza.FactilizaClient()).enviar_comprobante(payload)

    comprobante.respuesta_proveedor = respuesta.crudo
    comprobante.detalle_emision = respuesta.mensaje[:1000] if respuesta.mensaje else None
    if not respuesta.aceptado:
        comprobante.estado_emision = "rechazado"
        return comprobante

    comprobante.estado_emision = "aceptado"
    comprobante.hash_proveedor = respuesta.hash
    venta = VentaRepo(session).get(comprobante.venta_id)
    if venta is not None and venta.estado == "pagada":
        venta.estado = "facturada"
    event_bus.publish(
        "sales.comprobante_emitido",
        {
            "comprobante_id": str(comprobante.id),
            "venta_id": str(comprobante.venta_id),
            "empresa_id": str(comprobante.empresa_id),
            "tipo": comprobante.tipo,
            "serie_numero": f"{comprobante.serie}-{comprobante.correlativo:08d}",
            "total": str(venta.total if venta else Decimal(0)),
        },
        session=session,
    )
    return comprobante


FORMATOS_DESCARGA = ("pdf", "xml", "cdr")


def descargar_documento(
    session: Session,
    comprobante_id: uuid.UUID,
    formato: str,
    client: factiliza.FactilizaClient | None = None,
) -> factiliza.DocumentoDescargado:
    """Baja el PDF, el XML firmado o el CDR de un comprobante aceptado.

    Se pide al proveedor en el momento y no se guarda: Factiliza es el
    emisor y su copia es la buena. Guardar una nuestra agregaría un archivo
    que puede quedar desincronizado del que SUNAT tiene, sin ganar nada
    mientras el proveedor siga activo — cuando haga falta archivarlo por
    contingencia, va a `archivo` con su hash (ver ROADMAP).

    Solo de un comprobante `aceptado`: antes de eso no hay XML firmado ni
    CDR que bajar, y el PDF sería de un documento que SUNAT no reconoce.
    """
    if formato not in FORMATOS_DESCARGA:
        raise ReglaNegocio(f"formato no descargable: {formato}")
    comprobante = ComprobanteRepo(session).get(comprobante_id)
    if comprobante is None:
        raise NoEncontrado("comprobante no encontrado")
    if comprobante.direccion != "emitido":
        raise Conflicto("solo se descarga un comprobante propio, no uno recibido")
    if comprobante.estado_emision != "aceptado":
        raise Conflicto(
            f"el comprobante está {comprobante.estado_emision}: sin aceptación de "
            "SUNAT no hay documento que descargar"
        )
    return (client or factiliza.FactilizaClient()).descargar(
        formato,
        _tipo_doc_sunat(comprobante.tipo),
        comprobante.serie,
        comprobante.correlativo,
    )


def _tipo_doc_sunat(tipo: str) -> str:
    return {
        "factura": factiliza.TIPO_DOC_FACTURA,
        "boleta": factiliza.TIPO_DOC_BOLETA,
        "nc": factiliza.TIPO_DOC_NOTA_CREDITO,
    }[tipo]
