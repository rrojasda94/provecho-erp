"""Contrato de sincronización de `inventory` hacia el hub (ADR-009).

El hub necesita stock porque el listener `sales.venta_confirmada` corre en
su propio proceso: si el catálogo estuviera replicado pero el stock no, la
primera venta offline fallaría al descontar insumos.

`stock` es el único recurso que el hub también escribe localmente (cada
venta lo mueve). La nube gana en el pull, y eso es correcto **porque el
ciclo empuja antes de jalar**: para cuando el hub lee el stock de la nube,
la nube ya procesó las ventas del corte y ambos valores convergen.

Desde 2026-08-07 también viaja el **ciclo de abastecimiento**: el local
tiene que poder ver qué pidió y **recibir lo que llegó** durante un corte,
que es el momento en que más falta hace —el camión no espera a que vuelva
el internet—. Vale la misma regla que para `stock`: lo escribe el hub, la
nube gana en el pull, y converge porque el ciclo empuja primero.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.sync.contratos import AlcanceHub, RecursoSync
from src.core.sync.tiempo import a_utc, para_dialecto
from src.modules.inventory.application import conteos as conteos_uc
from src.modules.inventory.application import solicitudes as solicitudes_uc
from src.modules.inventory.application import transferencias as transferencias_uc
from src.modules.inventory.application.errors import AppError, NoEncontrado
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Conteo,
    ConteoItem,
    Lote,
    Receta,
    RecetaItem,
    ReservaStock,
    Sku,
    SolicitudInsumos,
    SolicitudItem,
    Stock,
    StockLote,
    Transferencia,
    TransferenciaItem,
    UnidadMedida,
)

# Almacén es organización transversal (data-model §1); vive en
# users/infrastructure por historia. Import de modelo (no dominio)
# permitido — mismo precedente que `application/listeners.py`.
from src.modules.inventory.infrastructure.repositories import (
    ConteoRepo,
    TransferenciaRepo,
)
from src.modules.users.infrastructure.models import Almacen


def _articulos_de_la_empresa(alcance):
    return select(Articulo.id).where(Articulo.empresa_id == alcance.empresa_id)


def _almacenes_de_la_sucursal(alcance):
    return select(Almacen.id).where(Almacen.sucursal_id == alcance.sucursal_id)


RECURSOS = (
    RecursoSync(
        nombre="categoria_udm",
        modelo=CategoriaUdm,
        campos=("id", "nombre", "unidad_base_id", "updated_at"),
        filtro=lambda q, a: q,
        motivo="Catálogo global de unidades; `unidad_medida` cuelga de acá.",
    ),
    RecursoSync(
        nombre="unidad_medida",
        modelo=UnidadMedida,
        campos=("id", "categoria_udm_id", "nombre", "ratio", "updated_at"),
        filtro=lambda q, a: q,
        motivo="`articulo` y `receta` la referencian.",
    ),
    RecursoSync(
        nombre="categoria",
        modelo=Categoria,
        campos=(
            "id",
            "empresa_id",
            "nombre",
            "asiento_contable_config",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Categoria.empresa_id == a.empresa_id),
        motivo="Agrupa artículos y rutea ítems a las pantallas de cocina.",
    ),
    RecursoSync(
        nombre="articulo",
        modelo=Articulo,
        campos=(
            "id",
            "empresa_id",
            "id_interno",
            "nombre",
            "categoria_id",
            "unidad_medida_id",
            "tipo",
            "costo_promedio",
            "archivado",
            "controla_lote",
            "dias_alerta_vencimiento",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Articulo.empresa_id == a.empresa_id),
        motivo="Insumos y empaques que consume cada venta.",
    ),
    RecursoSync(
        nombre="sku",
        modelo=Sku,
        campos=(
            "id",
            "articulo_id",
            "codigo",
            "codigo_barras",
            "prioridad",
            "activo",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Sku.articulo_id.in_(_articulos_de_la_empresa(a))),
        motivo="El movimiento de stock es por SKU, no por artículo.",
    ),
    RecursoSync(
        nombre="receta",
        modelo=Receta,
        campos=(
            "id",
            "empresa_id",
            "nombre",
            "rendimiento_cantidad",
            "rendimiento_unidad_medida_id",
            "flexible",
            "criterio_ajuste",
            "articulo_id",
            "updated_at",
        ),
        # Desde 2026-08-06 `receta` tiene columna de empresa, así que el hub
        # de una sucursal recibe solo las de su empresa. Antes se replicaba
        # completa por falta de esa columna.
        filtro=lambda q, a: q.where(Receta.empresa_id == a.empresa_id),
        motivo="Sin la receta, la venta offline no sabe qué insumos descontar.",
    ),
    RecursoSync(
        nombre="receta_item",
        modelo=RecetaItem,
        campos=(
            "id",
            "receta_id",
            "articulo_id",
            "cantidad",
            "merma_pct",
            "expresion",
            "updated_at",
        ),
        # Cuelga de la receta: se acota por las de la empresa, no por sí
        # mismo — `receta_item` no tiene ni necesita columna de tenant.
        filtro=lambda q, a: q.where(
            RecetaItem.receta_id.in_(
                select(Receta.id).where(Receta.empresa_id == a.empresa_id)
            )
        ),
        motivo="El detalle de la receta: qué y cuánto se descuenta.",
    ),
    RecursoSync(
        nombre="stock",
        modelo=Stock,
        campos=(
            "id",
            "almacen_id",
            "sku_id",
            "cantidad",
            "stock_minimo",
            "stock_maximo",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Stock.almacen_id.in_(_almacenes_de_la_sucursal(a))),
        motivo="Cantidad disponible en el local; la venta la descuenta offline.",
    ),
    RecursoSync(
        nombre="lote",
        modelo=Lote,
        campos=(
            "id",
            "articulo_id",
            "codigo",
            "fecha_vencimiento",
            "fecha_elaboracion",
            "origen",
            "referencia",
            "condicion_almacenamiento",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Lote.articulo_id.in_(_articulos_de_la_empresa(a))),
        motivo="Sin la fecha de vencimiento, la venta offline no puede aplicar FEFO.",
    ),
    RecursoSync(
        nombre="stock_lote",
        modelo=StockLote,
        campos=(
            "id",
            "almacen_id",
            "sku_id",
            "lote_id",
            "cantidad",
            "estado",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(
            StockLote.almacen_id.in_(_almacenes_de_la_sucursal(a))
        ),
        motivo=(
            "Detalle por lote del stock local: el hub elige el lote igual que "
            "la nube. Mismo criterio que `stock` — el hub lo escribe, la nube "
            "gana en el pull porque el ciclo empuja antes de jalar."
        ),
    ),
    RecursoSync(
        nombre="reserva_stock",
        modelo=ReservaStock,
        campos=(
            "id",
            "almacen_id",
            "sku_id",
            "lote_id",
            "cantidad",
            "tipo",
            "referencia_id",
            "motivo",
            "estado",
            "creado_por",
            "liberado_por",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(
            ReservaStock.almacen_id.in_(_almacenes_de_la_sucursal(a))
        ),
        motivo=(
            "Sin las reservas del local, su `disponible` offline sería el "
            "físico entero y comprometería stock ya prometido."
        ),
    ),
    RecursoSync(
        nombre="solicitud_insumos",
        modelo=SolicitudInsumos,
        campos=(
            "id",
            "almacen_solicitante_id",
            "almacen_abastecedor_id",
            "estado",
            "solicitado_por",
            "aprobado_por",
            "observacion",
            "updated_at",
        ),
        # Las que **pidió** este local. Las de otras sucursales no le
        # importan, y las del central tampoco: no es su pedido.
        filtro=lambda q, a: q.where(
            SolicitudInsumos.almacen_solicitante_id.in_(_almacenes_de_la_sucursal(a))
        ),
        motivo="Qué pidió el local y en qué estado va, aunque se corte.",
    ),
    RecursoSync(
        nombre="solicitud_item",
        modelo=SolicitudItem,
        campos=(
            "id",
            "solicitud_id",
            "sku_id",
            "cantidad_solicitada",
            "cantidad_aprobada",
            "cantidad_despachada",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(
            SolicitudItem.solicitud_id.in_(
                select(SolicitudInsumos.id).where(
                    SolicitudInsumos.almacen_solicitante_id.in_(
                        _almacenes_de_la_sucursal(a)
                    )
                )
            )
        ),
        motivo="El detalle: lo pedido, lo aprobado y lo que el central despachó.",
    ),
    RecursoSync(
        nombre="transferencia",
        modelo=Transferencia,
        campos=(
            "id",
            "origen_almacen_id",
            "destino_almacen_id",
            "solicitud_id",
            "estado",
            "despachado_por",
            "recibido_por",
            "transportista_id",
            "recibida_at",
            "observacion",
            "updated_at",
        ),
        # Las que **entran** al local: son las que va a tener que recibir, y
        # recibir es justo lo que no puede esperar a que vuelva el internet.
        # Las que salen de acá (lateral) las crea el propio hub.
        filtro=lambda q, a: q.where(
            Transferencia.destino_almacen_id.in_(_almacenes_de_la_sucursal(a))
        ),
        motivo="Lo que viene en camino: sin esto el local no puede recibir offline.",
    ),
    RecursoSync(
        nombre="transferencia_item",
        modelo=TransferenciaItem,
        campos=(
            "id",
            "transferencia_id",
            "sku_id",
            "lote_id",
            "cantidad_enviada",
            "cantidad_recibida",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(
            TransferenciaItem.transferencia_id.in_(
                select(Transferencia.id).where(
                    Transferencia.destino_almacen_id.in_(_almacenes_de_la_sucursal(a))
                )
            )
        ),
        motivo="Qué lotes trae el camión: el destino recibe los mismos que salieron.",
    ),
)


# --- Camino ascendente: lo que el local hizo durante el corte ----------------
#
# El hub no solo vende offline: **pide insumos, recibe el camión y cuenta el
# almacén**, y las tres cosas pasan justo cuando el internet no está. Lo que
# sube son esas tres, y ninguna se copia como fila cruda — cada una se
# reproduce por su caso de uso en la nube, con sus reglas y sus eventos.
#
# Las tres son de naturaleza distinta y eso decide cómo se reproducen:
#
# - **Solicitud**: nace en el hub. Viaja con su `id` client-generado, igual
#   que una venta, y crearla de nuevo con el mismo id no la duplica.
# - **Recepción**: NO nace en el hub. La transferencia la creó el central en
#   la nube; el hub solo la recibe. Lo que sube es el cambio de estado, y
#   reproducirlo dos veces tiene que ser inocuo, no un error.
# - **Conteo**: nace en el hub y se reproduce en tres pasos (abrir, anotar,
#   cerrar) porque el cierre es el que genera los ajustes en la nube.

RECURSO_PUSH = "inventory"


def _solicitud_a_dict(session: Session, solicitud: SolicitudInsumos) -> dict:
    items = session.scalars(
        select(SolicitudItem).where(SolicitudItem.solicitud_id == solicitud.id)
    )
    return {
        "id": str(solicitud.id),
        "almacen_solicitante_id": str(solicitud.almacen_solicitante_id),
        "almacen_abastecedor_id": str(solicitud.almacen_abastecedor_id),
        "solicitado_por": str(solicitud.solicitado_por),
        "observacion": solicitud.observacion,
        "items": [
            {"sku_id": str(i.sku_id), "cantidad": str(i.cantidad_solicitada)}
            for i in items
        ],
    }


def _recepcion_a_dict(session: Session, transferencia: Transferencia) -> dict:
    items = session.scalars(
        select(TransferenciaItem).where(
            TransferenciaItem.transferencia_id == transferencia.id
        )
    )
    return {
        "id": str(transferencia.id),
        "recibido_por": str(transferencia.recibido_por),
        "recibidas": [
            {"item_id": str(i.id), "cantidad": str(i.cantidad_recibida)}
            for i in items
            if i.cantidad_recibida is not None
        ],
    }


def _conteo_a_dict(session: Session, conteo: Conteo) -> dict:
    items = session.scalars(
        select(ConteoItem).where(
            ConteoItem.conteo_id == conteo.id, ConteoItem.cantidad_contada.isnot(None)
        )
    )
    return {
        "id": str(conteo.id),
        "almacen_id": str(conteo.almacen_id),
        "categoria_id": str(conteo.categoria_id) if conteo.categoria_id else None,
        "tipo": conteo.tipo,
        "estado": conteo.estado,
        "abierto_por": str(conteo.abierto_por),
        "cerrado_por": str(conteo.cerrado_por) if conteo.cerrado_por else None,
        "observacion": conteo.observacion,
        "items": [
            {"sku_id": str(i.sku_id), "cantidad": str(i.cantidad_contada)}
            for i in items
        ],
    }


def _tope(filas: list, limite: int, marcas: list) -> datetime | None:
    """Si el lote salió truncado, la marca no puede pasar de la última fila
    incluida — lo que quedó afuera se perdería. Mismo criterio que `sales`."""
    return max(marcas) if len(filas) >= limite and marcas else None


def pendientes(
    session: Session, alcance: AlcanceHub, desde: datetime | None, limite: int
) -> dict:
    """Solicitudes, recepciones y conteos del local desde `desde`."""
    almacenes = _almacenes_de_la_sucursal(alcance)
    q_solicitudes = select(SolicitudInsumos).where(
        SolicitudInsumos.almacen_solicitante_id.in_(almacenes)
    )
    # Solo las YA recibidas: una transferencia en tránsito no tiene nada que
    # reproducir, y una parcial todavía no cerró su ciclo.
    q_recepciones = select(Transferencia).where(
        Transferencia.destino_almacen_id.in_(almacenes),
        Transferencia.estado == "recibida",
    )
    # El conteo sube **cerrado**: uno abierto todavía se está contando, y
    # reproducirlo a medias en la nube generaría ajustes por ítems que nadie
    # miró.
    q_conteos = select(Conteo).where(
        Conteo.almacen_id.in_(almacenes), Conteo.estado.in_(("cerrado", "anulado"))
    )
    if desde is not None:
        piso = para_dialecto(session, desde)
        q_solicitudes = q_solicitudes.where(SolicitudInsumos.updated_at >= piso)
        q_recepciones = q_recepciones.where(Transferencia.updated_at >= piso)
        q_conteos = q_conteos.where(Conteo.updated_at >= piso)

    solicitudes = list(
        session.scalars(q_solicitudes.order_by(SolicitudInsumos.updated_at).limit(limite))
    )
    recepciones = list(
        session.scalars(q_recepciones.order_by(Transferencia.updated_at).limit(limite))
    )
    conteos = list(session.scalars(q_conteos.order_by(Conteo.updated_at).limit(limite)))

    marcas = {
        "solicitudes": [a_utc(s.updated_at) for s in solicitudes],
        "recepciones": [a_utc(t.updated_at) for t in recepciones],
        "conteos": [a_utc(c.updated_at) for c in conteos],
    }
    topes = [
        t
        for t in (
            _tope(solicitudes, limite, marcas["solicitudes"]),
            _tope(recepciones, limite, marcas["recepciones"]),
            _tope(conteos, limite, marcas["conteos"]),
        )
        if t is not None
    ]
    todas = [m for grupo in marcas.values() for m in grupo]
    marca = min(topes) if topes else (max(todas) if todas else None)

    return {
        "solicitudes": [_solicitud_a_dict(session, s) for s in solicitudes],
        "recepciones": [_recepcion_a_dict(session, t) for t in recepciones],
        "conteos": [_conteo_a_dict(session, c) for c in conteos],
        "marca": marca.isoformat() if marca else None,
    }


def hay_pendientes(lote: dict) -> int:
    return len(lote["solicitudes"]) + len(lote["recepciones"]) + len(lote["conteos"])


_FALLO = object()


def _intentar(session: Session, resumen: dict, tipo: str, ident: str, funcion, datos):
    """Aplica y commitea un ítem. Si la nube lo rechaza, deshace SOLO ese
    ítem y lo anota — el resto del lote sigue su curso. Mismo criterio que
    `sales`: perder un pedido en silencio sería peor que rechazarlo fuerte."""
    try:
        resultado = funcion(session, datos)
        session.commit()
        return resultado
    except (AppError, ValueError, SQLAlchemyError) as e:
        session.rollback()
        resumen["errores"].append({"tipo": tipo, "id": ident, "detalle": str(e)})
        return _FALLO


def _aplicar_solicitud(session: Session, datos: dict) -> None:
    solicitudes_uc.crear_solicitud(
        session,
        id=uuid.UUID(datos["id"]),
        almacen_solicitante_id=uuid.UUID(datos["almacen_solicitante_id"]),
        almacen_abastecedor_id=uuid.UUID(datos["almacen_abastecedor_id"]),
        solicitado_por=uuid.UUID(datos["solicitado_por"]),
        observacion=datos.get("observacion"),
        items=[
            (uuid.UUID(i["sku_id"]), Decimal(i["cantidad"])) for i in datos["items"]
        ],
    )


def _aplicar_recepcion(session: Session, datos: dict) -> None:
    """La transferencia es de la nube; lo que sube es que ya llegó.

    Si la nube la tiene recibida, no es error: el lote se reenvía entero
    cuando **otro** ítem falla, así que reproducir una recepción ya aplicada
    tiene que ser inocuo o el recurso se traba para siempre.
    """
    transferencia = TransferenciaRepo(session).get(uuid.UUID(datos["id"]))
    if transferencia is None:
        raise NoEncontrado("transferencia no encontrada en la nube")
    if transferencia.estado == "recibida":
        return
    transferencias_uc.recibir(
        session,
        transferencia.id,
        uuid.UUID(datos["recibido_por"]),
        {
            uuid.UUID(r["item_id"]): Decimal(r["cantidad"])
            for r in datos["recibidas"]
        },
    )


def _aplicar_conteo(session: Session, datos: dict) -> None:
    """Tres pasos, porque el cierre es el que genera los ajustes en la nube.

    Un conteo anulado en el hub se reproduce como anulado: no genera ajustes
    ni corre el calendario, exactamente igual que si se hubiera anulado acá.
    """
    conteo_id = uuid.UUID(datos["id"])
    conteos_uc.abrir_conteo(
        session,
        id=conteo_id,
        almacen_id=uuid.UUID(datos["almacen_id"]),
        categoria_id=(
            uuid.UUID(datos["categoria_id"]) if datos.get("categoria_id") else None
        ),
        tipo=datos["tipo"],
        abierto_por=uuid.UUID(datos["abierto_por"]),
        observacion=datos.get("observacion"),
    )
    conteo = ConteoRepo(session).get(conteo_id)
    if conteo.estado != "abierto":
        return  # ya se reprodujo en un lote anterior

    if datos["estado"] == "anulado":
        conteos_uc.anular_conteo(
            session,
            conteo_id,
            uuid.UUID(datos["cerrado_por"] or datos["abierto_por"]),
            datos.get("observacion") or "anulado en el local sin conexión",
        )
        return

    conteos_uc.registrar_cantidades(
        session,
        conteo_id,
        [(uuid.UUID(i["sku_id"]), Decimal(i["cantidad"])) for i in datos["items"]],
    )
    conteos_uc.cerrar_conteo(
        session, conteo_id, uuid.UUID(datos["cerrado_por"] or datos["abierto_por"])
    )


def aplicar(session: Session, lote: dict, alcance: AlcanceHub) -> tuple[dict, list]:
    """Reproduce en la nube el ciclo de abastecimiento del corte.

    Devuelve `(resumen, [])`: la lista vacía es el hueco donde `sales`
    devuelve los comprobantes a encolar después del commit. Inventory no
    tiene nada que encolar —la guía la emite quien despacha, no quien
    recibe—, pero el contrato es el mismo para que el motor no tenga que
    saber de quién es el lote.
    """
    resumen = {"solicitudes": 0, "recepciones": 0, "conteos": 0, "errores": []}
    for datos in lote.get("solicitudes") or []:
        if _intentar(
            session, resumen, "solicitud", datos["id"], _aplicar_solicitud, datos
        ) is not _FALLO:
            resumen["solicitudes"] += 1
    for datos in lote.get("recepciones") or []:
        if _intentar(
            session, resumen, "recepcion", datos["id"], _aplicar_recepcion, datos
        ) is not _FALLO:
            resumen["recepciones"] += 1
    for datos in lote.get("conteos") or []:
        if _intentar(
            session, resumen, "conteo", datos["id"], _aplicar_conteo, datos
        ) is not _FALLO:
            resumen["conteos"] += 1
    return resumen, []
