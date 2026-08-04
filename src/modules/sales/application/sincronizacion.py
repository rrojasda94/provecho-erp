"""Contrato de sincronización de `sales` con el hub de sucursal (ADR-009).

Dos direcciones, dos responsabilidades:

- **Descendente** (`RECURSOS`): catálogo comercial que el PDV necesita para
  vender durante un corte.
- **Ascendente** (`pendientes` / `aplicar`): las ventas, cobros y
  anulaciones que ocurrieron offline se reproducen en la nube **por los
  mismos casos de uso** que atiende un PDV en línea. No hay una vía
  paralela que escriba filas crudas: la venta sincronizada pasa por las
  mismas validaciones, publica los mismos eventos (y por eso la nube
  descuenta su propio stock y emite el comprobante) y respeta la misma
  idempotencia.

Por eso el hub NO empuja movimientos de inventario: el listener de la nube
los genera al recibir la venta. Empujarlos además duplicaría el consumo.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.sync.contratos import AlcanceHub, RecursoSync
from src.core.sync.tiempo import a_utc, para_dialecto
from src.modules.sales.application import ventas as ventas_uc
from src.modules.sales.application.errors import AppError
from src.modules.sales.infrastructure.models import (
    KdsPantalla,
    ListaPrecio,
    MedioPago,
    Pago,
    Precio,
    ProductoComercial,
    ProductoComercialExtra,
    ProductoOpcionGrupo,
    PuntoVenta,
    Venta,
)
from src.modules.sales.infrastructure.repositories import VentaRepo
from src.modules.users.infrastructure.models import Sucursal

log = logging.getLogger("provecho.sync")

# Nombre del recurso de push en `sync_watermark`: ventas y pagos comparten
# marca. Son la misma unidad de trabajo y reenviar de más es inofensivo
# (todo el camino ascendente es idempotente).
RECURSO_PUSH = "sales"


def _marca_de_la_sucursal(alcance: AlcanceHub):
    return select(Sucursal.marca_id).where(Sucursal.id == alcance.sucursal_id)


RECURSOS = (
    RecursoSync(
        nombre="producto_comercial",
        modelo=ProductoComercial,
        campos=(
            "id",
            "id_interno",
            "marca_id",
            "nombre",
            "categoria_id",
            "receta_id",
            "producto_padre_id",
            "orden",
            "activo",
            "margen_contribucion",
            "empaque_id",
            "modalidades_empaque",
            "es_extra",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(
            ProductoComercial.marca_id.in_(_marca_de_la_sucursal(a))
        ),
        motivo="La carta del local: sin esto no hay nada que vender offline.",
    ),
    RecursoSync(
        nombre="producto_comercial_extra",
        modelo=ProductoComercialExtra,
        campos=(
            "id",
            "producto_comercial_id",
            "extra_id",
            "maximo",
            "grupo_id",
            "updated_at",
        ),
        filtro=lambda q, a: q.join(
            ProductoComercial,
            ProductoComercial.id == ProductoComercialExtra.producto_comercial_id,
        ).where(ProductoComercial.marca_id.in_(_marca_de_la_sucursal(a))),
        motivo=(
            "Qué extra admite cada producto: sin esto el hub ofrecería extras "
            "imposibles o rechazaría los válidos durante el corte (RN-COM-021)."
        ),
    ),
    RecursoSync(
        nombre="producto_opcion_grupo",
        modelo=ProductoOpcionGrupo,
        campos=("id", "producto_comercial_id", "nombre", "minimo", "maximo",
                "orden", "updated_at"),
        filtro=lambda q, a: q.join(
            ProductoComercial,
            ProductoComercial.id == ProductoOpcionGrupo.producto_comercial_id,
        ).where(ProductoComercial.marca_id.in_(_marca_de_la_sucursal(a))),
        motivo=(
            "Qué grupo de extras es obligatorio: sin esto el hub aceptaría "
            "durante el corte pedidos que la nube rechaza (RN-COM-023)."
        ),
    ),
    RecursoSync(
        nombre="lista_precio",
        modelo=ListaPrecio,
        campos=(
            "id",
            "marca_id",
            "nombre",
            "sucursal_id",
            "canal",
            "modalidad",
            "es_promocional",
            "vigente_desde",
            "vigente_hasta",
            "activa",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(ListaPrecio.marca_id.in_(_marca_de_la_sucursal(a))),
        motivo=(
            "El precio lo fija el servidor (RN-PRC-003): sin las listas, el hub "
            "no puede cotizar una venta durante el corte."
        ),
    ),
    RecursoSync(
        nombre="precio",
        modelo=Precio,
        campos=("id", "lista_precio_id", "producto_comercial_id", "monto", "updated_at"),
        filtro=lambda q, a: q.where(
            Precio.lista_precio_id.in_(
                select(ListaPrecio.id).where(
                    ListaPrecio.marca_id.in_(_marca_de_la_sucursal(a))
                )
            )
        ),
        motivo="El monto de cada producto dentro de esas listas.",
    ),
    RecursoSync(
        nombre="medio_pago",
        modelo=MedioPago,
        campos=(
            "id",
            "empresa_id",
            "nombre",
            "direccion",
            "tipo",
            "comision_pct",
            "activo",
            "activa_promocion",
            "lista_precio_credito_id",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(MedioPago.empresa_id == a.empresa_id),
        motivo="Cobrar offline exige el catálogo de medios de pago de la empresa.",
    ),
    RecursoSync(
        nombre="punto_venta",
        modelo=PuntoVenta,
        campos=(
            "id",
            "sucursal_id",
            "canal",
            "hardware_id",
            "serie_boleta",
            "serie_factura",
            "modalidades_habilitadas",
            "datos_minimos_por_modalidad",
            "politica_pago",
            "kpis",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(PuntoVenta.sucursal_id == a.sucursal_id),
        motivo="Cada caja/kiosko del local y su política de cobro.",
    ),
    RecursoSync(
        nombre="kds_pantalla",
        modelo=KdsPantalla,
        campos=(
            "id",
            "sucursal_id",
            "nombre",
            "tipo",
            "categoria_ids",
            "activo",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(KdsPantalla.sucursal_id == a.sucursal_id),
        motivo="El KDS sigue operando durante el corte (alcance offline del ADR).",
    ),
)


# --- Ascendente: hub → nube --------------------------------------------------
def _venta_a_dict(session: Session, venta: Venta) -> dict:
    return {
        "id": str(venta.id),
        "sucursal_id": str(venta.sucursal_id),
        "punto_venta_id": str(venta.punto_venta_id),
        "canal": venta.canal,
        "modalidad": venta.modalidad,
        "usuario_id": str(venta.usuario_id),
        "cliente_id": str(venta.cliente_id) if venta.cliente_id else None,
        "referencia_atencion": venta.referencia_atencion,
        "mesa_id": str(venta.mesa_id) if venta.mesa_id else None,
        "comensales": venta.comensales,
        "idempotency_key": venta.idempotency_key,
        "fecha_orden": venta.fecha_orden.isoformat(),
        "numero_orden": venta.numero_orden,
        "estado": venta.estado,
        # El descuento viaja con su motivo y autorizador: reconstruirlo en la
        # nube a partir del total dejaría la venta sin trazabilidad.
        "descuento_modo": venta.descuento_modo,
        "descuento_valor": (
            str(venta.descuento_valor) if venta.descuento_valor is not None else None
        ),
        "descuento_motivo": venta.descuento_motivo,
        "descuento_autorizado_por": (
            str(venta.descuento_autorizado_por)
            if venta.descuento_autorizado_por
            else None
        ),
        # Los extras viajan ANIDADOS bajo su línea padre, igual que en el
        # request de creación: aplanarlos haría que el replay los recreara
        # como líneas sueltas y se perdería de qué plato colgaban.
        "items": _items_a_dict(VentaRepo(session).items(venta.id)),
    }


def _items_a_dict(filas: list) -> list[dict]:
    def basico(it) -> dict:
        return {
            "producto_comercial_id": str(it.producto_comercial_id),
            "cantidad": str(it.cantidad),
            "precio_unitario": str(it.precio_unitario),
            "descuento": str(it.descuento),
            "grupo_cobro": it.grupo_cobro,
        }

    hijos: dict = {}
    for it in filas:
        if it.padre_venta_item_id:
            hijos.setdefault(it.padre_venta_item_id, []).append(it)
    salida = []
    for it in filas:
        if it.padre_venta_item_id:
            continue
        fila = basico(it)
        if it.id in hijos:
            # El extra se guarda con la cantidad TOTAL (por plato × platos),
            # pero el request la espera POR PLATO y la vuelve a multiplicar.
            # Sin dividir acá, cada sincronización duplicaría los extras.
            fila["extras"] = [
                {
                    **basico(h),
                    "cantidad": str(
                        h.cantidad / it.cantidad if it.cantidad else h.cantidad
                    ),
                }
                for h in hijos[it.id]
            ]
        salida.append(fila)
    return salida


def _pago_a_dict(pago: Pago) -> dict:
    return {
        "id": str(pago.id),
        "venta_id": str(pago.venta_id),
        "medio_pago_id": str(pago.medio_pago_id),
        "monto": str(pago.monto),
        "grupo_cobro": pago.grupo_cobro,
        "idempotency_key": pago.idempotency_key,
        "referencia_externa": pago.referencia_externa,
    }


def _tope(filas: list, limite: int, marcas: list[datetime]) -> datetime | None:
    """Si el lote salió truncado, la marca no puede pasar de la última fila
    incluida — lo que quedó afuera se perdería."""
    return max(marcas) if len(filas) >= limite and marcas else None


def pendientes(
    session: Session, alcance: AlcanceHub, desde: datetime | None, limite: int
) -> dict:
    """Ventas y pagos del local con `updated_at >= desde`, listos para
    reproducirse en la nube. Una venta anulada vuelve a salir (su
    `updated_at` cambió) y así la anulación viaja sin payload aparte."""
    consulta_ventas = select(Venta).where(Venta.sucursal_id == alcance.sucursal_id)
    consulta_pagos = (
        select(Pago)
        .join(Venta, Venta.id == Pago.venta_id)
        .where(Venta.sucursal_id == alcance.sucursal_id)
    )
    if desde is not None:
        limite_inferior = para_dialecto(session, desde)
        consulta_ventas = consulta_ventas.where(Venta.updated_at >= limite_inferior)
        consulta_pagos = consulta_pagos.where(Pago.updated_at >= limite_inferior)

    ventas = list(
        session.scalars(consulta_ventas.order_by(Venta.updated_at).limit(limite))
    )
    pagos = list(
        session.scalars(consulta_pagos.order_by(Pago.updated_at).limit(limite))
    )
    marcas_ventas = [a_utc(v.updated_at) for v in ventas]
    marcas_pagos = [a_utc(p.updated_at) for p in pagos]

    topes = [
        t
        for t in (
            _tope(ventas, limite, marcas_ventas),
            _tope(pagos, limite, marcas_pagos),
        )
        if t is not None
    ]
    todas = marcas_ventas + marcas_pagos
    marca = min(topes) if topes else (max(todas) if todas else None)

    return {
        "ventas": [_venta_a_dict(session, v) for v in ventas],
        "pagos": [_pago_a_dict(p) for p in pagos],
        "marca": marca.isoformat() if marca else None,
    }


_FALLO = object()


def _intentar(session: Session, resumen: dict, tipo: str, ident: str, funcion, datos):
    """Aplica y commitea un ítem. Si la nube lo rechaza, deshace SOLO ese
    ítem y lo anota — el resto del lote sigue su curso."""
    try:
        resultado = funcion(session, datos)
        session.commit()
        return resultado
    except (AppError, ValueError, SQLAlchemyError) as e:
        session.rollback()
        resumen["errores"].append({"tipo": tipo, "id": ident, "detalle": str(e)})
        return _FALLO


def _crear(session: Session, datos: dict) -> None:
    ventas_uc.crear_venta(
        session,
        id=uuid.UUID(datos["id"]),
        sucursal_id=uuid.UUID(datos["sucursal_id"]),
        punto_venta_id=uuid.UUID(datos["punto_venta_id"]),
        canal=datos["canal"],
        modalidad=datos["modalidad"],
        usuario_id=uuid.UUID(datos["usuario_id"]),
        idempotency_key=datos["idempotency_key"],
        items=[
            {
                "producto_comercial_id": uuid.UUID(it["producto_comercial_id"]),
                "cantidad": Decimal(it["cantidad"]),
                "precio_unitario": Decimal(it["precio_unitario"]),
                "descuento": Decimal(it["descuento"]),
                # Los lotes emitidos antes del cobro dividido no traen la
                # clave: esa venta tenía una sola cuenta.
                "grupo_cobro": it.get("grupo_cobro", 1),
                "extras": [
                    {
                        "producto_comercial_id": uuid.UUID(
                            ex["producto_comercial_id"]
                        ),
                        "cantidad": Decimal(ex["cantidad"]),
                        "precio_unitario": Decimal(ex["precio_unitario"]),
                        "descuento": Decimal(ex.get("descuento") or 0),
                    }
                    for ex in it.get("extras") or []
                ],
            }
            for it in datos["items"]
        ],
        cliente_id=uuid.UUID(datos["cliente_id"]) if datos.get("cliente_id") else None,
        referencia_atencion=datos.get("referencia_atencion"),
        mesa_id=uuid.UUID(datos["mesa_id"]) if datos.get("mesa_id") else None,
        comensales=datos.get("comensales"),
        fecha_orden=date.fromisoformat(datos["fecha_orden"]),
        numero_orden=datos["numero_orden"],
    )
    if datos.get("descuento_modo"):
        # Se reaplica tal cual se autorizó en el local; el motivo y el
        # supervisor viajan con la venta, no se re-piden en la nube.
        ventas_uc.aplicar_descuento(
            session,
            venta_id=uuid.UUID(datos["id"]),
            modo=datos["descuento_modo"],
            valor=Decimal(datos["descuento_valor"]),
            motivo=datos.get("descuento_motivo"),
            autorizado_por=uuid.UUID(datos["descuento_autorizado_por"]),
        )


def _cobrar(session: Session, datos: dict):
    return ventas_uc.registrar_pago(
        session,
        id=uuid.UUID(datos["id"]),
        venta_id=uuid.UUID(datos["venta_id"]),
        medio_pago_id=uuid.UUID(datos["medio_pago_id"]),
        monto=Decimal(datos["monto"]),
        grupo_cobro=datos.get("grupo_cobro", 1),
        idempotency_key=datos["idempotency_key"],
        referencia_externa=datos.get("referencia_externa"),
        # El turno de caja vive en el hub y no se replica todavía: exigirlo
        # acá rechazaría un cobro que ya ocurrió en la sucursal.
        exigir_caja_abierta=False,
    )


def _anular(session: Session, datos: dict):
    return ventas_uc.anular_venta(
        session, uuid.UUID(datos["id"]), uuid.UUID(datos["usuario_id"])
    )


def _aplicar_ventas(
    session: Session, filas: list[dict], alcance: AlcanceHub, resumen: dict
) -> list[dict]:
    """Crea las ventas y devuelve las que además hay que anular."""
    anular = []
    for datos in filas:
        if datos["sucursal_id"] != str(alcance.sucursal_id):
            resumen["errores"].append(
                {"tipo": "venta", "id": datos["id"], "detalle": "fuera de la sucursal del hub"}
            )
            continue
        if _intentar(session, resumen, "venta", datos["id"], _crear, datos) is _FALLO:
            continue
        resumen["ventas"] += 1
        if datos["estado"] == "anulada":
            anular.append(datos)
    return anular


def _aplicar_pagos(
    session: Session, filas: list[dict], resumen: dict
) -> list[uuid.UUID]:
    """Cobra y junta los comprobantes que quedaron pendientes de emisión."""
    comprobantes = []
    for datos in filas:
        resultado = _intentar(session, resumen, "pago", datos["id"], _cobrar, datos)
        if resultado is _FALLO:
            continue
        resumen["pagos"] += 1
        _, _, comprobante = resultado
        if comprobante is not None:
            comprobantes.append(comprobante.id)
    return comprobantes


def _aplicar_anulaciones(session: Session, filas: list[dict], resumen: dict) -> None:
    for datos in filas:
        if VentaRepo(session).get(uuid.UUID(datos["id"])).estado == "anulada":
            continue
        if _intentar(session, resumen, "anulacion", datos["id"], _anular, datos) is not _FALLO:
            resumen["anuladas"] += 1


def aplicar(
    session: Session, lote: dict, alcance: AlcanceHub
) -> tuple[dict, list[uuid.UUID]]:
    """Reproduce el lote del hub en la nube. Devuelve el resumen y los
    comprobantes que quedaron pendientes de emisión (el router los encola
    después — el worker solo ve filas confirmadas).

    **Un commit por ítem**, no uno por lote: cada venta del hub es una
    unidad de trabajo independiente, igual que si el PDV la hubiera
    posteado en su momento. Así una venta que la nube rechaza (un producto
    descontinuado, un correlativo ocupado) no arrastra a las demás ni
    obliga a reprocesar un lote entero de una jornada.
    """
    resumen = {"ventas": 0, "pagos": 0, "anuladas": 0, "errores": []}
    anular = _aplicar_ventas(session, lote.get("ventas", []), alcance, resumen)
    comprobantes = _aplicar_pagos(session, lote.get("pagos", []), resumen)
    # Al final: una venta anulada offline igual tuvo que crearse primero.
    _aplicar_anulaciones(session, anular, resumen)

    if resumen["errores"]:
        log.warning("sync push: %s ítems rechazados", len(resumen["errores"]))
    return resumen, comprobantes
