"""Casos de uso de stock: consulta y registro de movimientos.

El stock nunca se edita directo — todo cambio pasa por
`movimiento_inventario`, que aquí se inserta y refleja en la fila `stock`.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import lotes as lotes_uc
from src.modules.inventory.application.errors import ReglaNegocio, StockInsuficiente
from src.modules.inventory.domain import rules
from src.modules.inventory.infrastructure.models import (
    Articulo,
    MovimientoInventario,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.inventory.infrastructure.repositories import (
    LoteRepo,
    MovimientoRepo,
    ReservaRepo,
    SkuRepo,
    StockRepo,
)

# Almacén es organización transversal (data-model §1); vive en
# users/infrastructure por historia. Import de modelo (no dominio)
# permitido — mismo precedente que `application/listeners.py`.
from src.modules.users.infrastructure.models import Almacen
from src.shared.paginacion import Paginacion, paginar


def aplicar_a_stock(
    session: Session, almacen_id: uuid.UUID, sku_id: uuid.UUID, delta: Decimal
) -> Stock:
    """Suma `delta` (con signo) a la fila de stock; la crea si no existe.
    Rechaza dejar la cantidad en negativo."""
    repo = StockRepo(session)
    stock = repo.get(almacen_id, sku_id, for_update=True)
    if stock is None:
        stock = repo.add(Stock(almacen_id=almacen_id, sku_id=sku_id, cantidad=Decimal(0)))
    nueva = stock.cantidad + delta
    if nueva < 0:
        raise StockInsuficiente(
            f"stock insuficiente: {stock.cantidad} disponible, se requieren {-delta}"
        )
    stock.cantidad = nueva
    return stock


def registrar_movimiento(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    tipo: str,
    usuario_id: uuid.UUID | None = None,
    referencia: str | None = None,
    motivo_ajuste: str | None = None,
    lote_id: uuid.UUID | None = None,
    motivo_lote: str | None = None,
    permitir_sin_lote: bool = False,
    id: uuid.UUID | None = None,
) -> tuple[MovimientoInventario, Stock]:
    """`cantidad` con signo: + ingreso, − salida.

    Si el artículo controla lote, el movimiento también mueve `stock_lote`:
    un ingreso sin `lote_id` entra al lote del día (nada queda fuera de la
    trazabilidad) y una salida sin `lote_id` se rechaza — esa debe pasar
    por `registrar_salida`, que reparte por FEFO (ADR-015).

    `id` explícito lo usa el cliente que ya generó el identificador del
    movimiento antes de que existiera la fila (ADR-009): así un movimiento
    registrado sin conexión conserva su identidad si más tarde se
    reproduce. Los movimientos que derivan de una venta NO se sincronizan
    —el listener de la nube los genera al recibirla, empujarlos además
    duplicaría el consumo—, ver `sales/application/sincronizacion.py`.
    """
    if tipo not in rules.TIPOS_MOVIMIENTO:
        raise ReglaNegocio(f"tipo de movimiento inválido: {tipo}")
    if not rules.signo_movimiento_valido(tipo, cantidad):
        raise ReglaNegocio(
            f"signo de cantidad ({cantidad}) inválido para tipo '{tipo}'"
        )
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    if lote_id is not None and articulo.id != _articulo_del_lote(session, lote_id):
        raise ReglaNegocio("el lote no pertenece al artículo del SKU")
    if articulo.controla_lote and lote_id is None:
        if cantidad > 0:
            lote_id = lotes_uc.crear_lote(
                session,
                articulo_id=articulo.id,
                origen="ajuste" if tipo == "ajuste" else "carga_inicial",
                referencia=referencia,
            ).id
        elif not permitir_sin_lote:
            raise ReglaNegocio(
                "salida de un artículo con control de lote exige lote: "
                "usar registrar_salida (FEFO)"
            )

    stock = aplicar_a_stock(session, almacen_id, sku_id, cantidad)
    _avisar_si_cruza_el_minimo(session, stock, cantidad, usuario_id)
    if lote_id is not None:
        lotes_uc.aplicar_a_lote(session, almacen_id, sku_id, lote_id, cantidad)
    mov = MovimientoRepo(session).add(
        MovimientoInventario(
            id=id or uuid.uuid4(),
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=cantidad,
            tipo=tipo,
            motivo_ajuste=motivo_ajuste,
            referencia=referencia,
            usuario_id=usuario_id,
            lote_id=lote_id,
            motivo_lote=motivo_lote,
        )
    )
    return mov, stock


def _exigir_motivo_del_override(
    session: Session,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    lote_id: uuid.UUID,
    motivo_lote: str | None,
    hoy: date | None,
    usuario_id: uuid.UUID | None = None,
) -> None:
    """Tomar el lote que FEFO ya sugería no es un override; tomar otro sí.

    Pedir motivo en los dos casos convertiría el campo en un trámite que se
    llena con cualquier cosa, y un motivo que nadie escribe en serio es peor
    que ninguno: da la apariencia de control.
    """
    if motivo_lote:
        return
    disponibles = lotes_uc.disponibles_fefo(
        session, almacen_id, sku_id, hoy, usuario_id=usuario_id
    )
    sugerido = disponibles[0].lote_id if disponibles else None
    if sugerido is not None and sugerido != lote_id:
        raise ReglaNegocio(
            "tomar un lote distinto del que sugiere FEFO exige motivo_lote"
        )


def _avisar_si_cruza_el_minimo(
    session: Session,
    stock: Stock,
    delta: Decimal,
    usuario_id: uuid.UUID | None = None,
) -> None:
    """Publica `inventory.stock_bajo_minimo` al **cruzar** el mínimo, no cada
    vez que se está por debajo.

    La diferencia es la que hace útil al aviso: un SKU bajo mínimo toda la
    semana dispararía un evento por cada venta hasta que nadie lo mire —el
    mismo modo de falla que el margen de ajuste sin piso—. Reponer y volver
    a caer sí avisa de nuevo, que es exactamente cuando hay que comprar.
    """
    if stock.stock_minimo is None or delta >= 0:
        return
    previa = stock.cantidad - delta
    if rules.stock_bajo(stock.cantidad, stock.stock_minimo) and not rules.stock_bajo(
        previa, stock.stock_minimo
    ):
        event_bus.publish(
            "inventory.stock_bajo_minimo",
            {
                "almacen_id": str(stock.almacen_id),
                "sku_id": str(stock.sku_id),
                "cantidad": str(stock.cantidad),
                "stock_minimo": str(stock.stock_minimo),
                # Quién hizo el movimiento que cruzó el mínimo. Nulo cuando
                # el movimiento no viene de una persona (una sincronización,
                # un listener): el reporte dirá «Sistema».
                "usuario_id": str(usuario_id) if usuario_id else None,
            },
            session=session,
        )


def _articulo_del_lote(session: Session, lote_id: uuid.UUID) -> uuid.UUID:
    lote = LoteRepo(session).get(lote_id)
    if lote is None:
        raise ReglaNegocio("lote no encontrado")
    return lote.articulo_id


def registrar_salida(
    session: Session,
    *,
    almacen_id: uuid.UUID,
    sku_id: uuid.UUID,
    cantidad: Decimal,
    tipo: str,
    usuario_id: uuid.UUID | None = None,
    referencia: str | None = None,
    motivo_ajuste: str | None = None,
    lote_id: uuid.UUID | None = None,
    motivo_lote: str | None = None,
    hoy: date | None = None,
) -> list[MovimientoInventario]:
    """Salida con `cantidad` POSITIVA; genera un movimiento por lote tomado.

    FEFO: vence antes, sale antes. Un `lote_id` explícito es el override
    del lote sugerido, y saltearse FEFO exige `motivo_lote` (RN-LOT-004). Si
    el artículo no controla lote, es un movimiento único como siempre.
    """
    if cantidad <= 0:
        raise ReglaNegocio(f"la salida exige cantidad positiva, llegó {cantidad}")
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    if lote_id is not None or not articulo.controla_lote:
        if lote_id is not None and articulo.controla_lote:
            _exigir_motivo_del_override(
                session, almacen_id, sku_id, lote_id, motivo_lote, hoy, usuario_id
            )
        mov, _ = registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-cantidad,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            lote_id=lote_id,
            motivo_lote=motivo_lote,
        )
        return [mov]

    # Comprobar el total ANTES de repartir: así una salida que no alcanza
    # falla entera, en vez de dejar consumidos los primeros lotes.
    total = StockRepo(session).get(almacen_id, sku_id)
    if total is None or total.cantidad < cantidad:
        disponible = total.cantidad if total else Decimal(0)
        raise StockInsuficiente(
            f"stock insuficiente: {disponible} disponible, se requieren {cantidad}"
        )

    disponibles = lotes_uc.disponibles_fefo(
        session, almacen_id, sku_id, hoy, usuario_id=usuario_id
    )
    asignaciones, faltante = rules.repartir_fefo(
        [(f.lote_id, f.cantidad) for f in disponibles], cantidad
    )
    movs = [
        registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-monto,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            lote_id=lid,
        )[0]
        for lid, monto in asignaciones
    ]
    if faltante > 0:
        # El total alcanza pero ningún lote lo respalda: stock cargado
        # antes de activar el control de lote, o todo lo demás bloqueado
        # por vencimiento. Se descuenta igual —la operación ya ocurrió— y
        # queda el movimiento sin lote como rastro de la discrepancia.
        mov, _ = registrar_movimiento(
            session,
            almacen_id=almacen_id,
            sku_id=sku_id,
            cantidad=-faltante,
            tipo=tipo,
            usuario_id=usuario_id,
            referencia=referencia,
            motivo_ajuste=motivo_ajuste,
            permitir_sin_lote=True,
        )
        movs.append(mov)
    return movs


def consultar_stock_pagina(
    session: Session,
    p: Paginacion,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    *,
    sucursal_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    bajo_minimo: bool | None = None,
    texto: str | None = None,
) -> dict:
    """Igual que `consultar_stock`, pero una página a la vez (ADR-026).

    El corte va sobre `stock`, y las reservas y los nombres se componen solo
    para las filas de esa página: es donde vive el volumen (un SKU por
    almacén).
    """
    pagina = paginar(
        session,
        StockRepo(session).q_list(
            almacen_id,
            empresa_id,
            sucursal_id=sucursal_id,
            categoria_id=categoria_id,
            bajo_minimo=bajo_minimo,
            q=texto,
        ),
        p,
    )
    pagina["items"] = _componer(
        session, pagina["items"], almacen_id, empresa_id, con_nombres=True
    )
    return pagina


def consultar_stock(
    session: Session,
    almacen_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> list[dict]:
    """`cantidad` es el físico; `disponible` descuenta las reservas activas
    (RN-INV-009) — es el número contra el que se compromete stock nuevo."""
    return _componer(
        session, StockRepo(session).list(almacen_id, empresa_id), almacen_id, empresa_id
    )


def detalle_sku(session: Session, sku_id: uuid.UUID) -> dict:
    """El SKU, su artículo y su saldo en cada almacén donde existe.

    Es a donde lleva `inventory.stock_bajo_minimo`: el que abre el reporte
    quiere ver qué es, cuánto queda y dónde, no encadenar tres pantallas.
    """
    sku = SkuRepo(session).get(sku_id)
    articulo = lotes_uc.articulo_de_sku(session, sku_id)
    filas = StockRepo(session).list(sku_id=sku_id)
    nombres = _nombres_de_almacen(session, [f.almacen_id for f in filas])
    return {
        "id": sku.id,
        "articulo_id": sku.articulo_id,
        "codigo": sku.codigo,
        "codigo_barras": sku.codigo_barras,
        "activo": sku.activo,
        "articulo": articulo,
        "stock": [
            {**fila, "almacen": nombres.get(fila["almacen_id"], "(borrado)")}
            for fila in _componer(session, filas, None, None)
        ],
    }


def _nombres_de_almacen(session: Session, ids) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return dict(
        session.execute(
            select(Almacen.id, Almacen.nombre).where(Almacen.id.in_(ids))
        ).all()
    )


def rotulos_de_sku(session: Session, ids) -> dict[uuid.UUID, dict]:
    """Cómo se llama cada SKU: su código, su artículo y la unidad en que se
    cuenta.

    Una consulta para todos, no una por fila. Es el mismo criterio que
    `_nombres_de_almacen`: la pantalla de stock pide 50 filas y resolver el
    nombre de a uno serían 150 viajes.
    """
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    filas = session.execute(
        select(
            Sku.id,
            Sku.codigo,
            Articulo.id,
            Articulo.nombre,
            UnidadMedida.nombre,
            UnidadMedida.decimales,
        )
        .join(Articulo, Articulo.id == Sku.articulo_id)
        .join(UnidadMedida, UnidadMedida.id == Articulo.unidad_medida_id)
        .where(Sku.id.in_(ids))
    ).all()
    return {
        sku_id: {
            "sku_codigo": codigo,
            "articulo_id": articulo_id,
            "articulo": articulo,
            "unidad": unidad,
            "decimales": decimales,
        }
        for sku_id, codigo, articulo_id, articulo, unidad, decimales in filas
    }


def _componer(
    session: Session,
    filas: list,
    almacen_id: uuid.UUID | None,
    empresa_id: uuid.UUID | None,
    *,
    con_nombres: bool = False,
) -> list[dict]:
    reservado: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    for r in ReservaRepo(session).activas(almacen_id, None, empresa_id):
        clave = (r.almacen_id, r.sku_id)
        reservado[clave] = reservado.get(clave, Decimal(0)) + r.cantidad
    # Los rótulos solo se piden cuando alguien los va a leer: los consumidores
    # internos (reservas, transferencias, conteos) trabajan con ids y pagarían
    # dos consultas de más por fila que nunca se dibuja.
    almacenes = _nombres_de_almacen(session, [f.almacen_id for f in filas]) if con_nombres else {}
    skus = rotulos_de_sku(session, [f.sku_id for f in filas]) if con_nombres else {}
    compuestas = []
    for s in filas:
        fila = {
            "almacen_id": s.almacen_id,
            "sku_id": s.sku_id,
            "cantidad": s.cantidad,
            "reservado": reservado.get((s.almacen_id, s.sku_id), Decimal(0)),
            "disponible": rules.disponible(
                s.cantidad, reservado.get((s.almacen_id, s.sku_id), Decimal(0))
            ),
            "stock_minimo": s.stock_minimo,
            "bajo_minimo": rules.stock_bajo(s.cantidad, s.stock_minimo),
        }
        if con_nombres:
            # "(borrado)" y no `None`: la fila de stock de un almacén dado de
            # baja sigue existiendo, y esconderla mentiría sobre el total.
            fila["almacen"] = almacenes.get(s.almacen_id, "(borrado)")
            fila.update(skus.get(s.sku_id, {}))
        compuestas.append(fila)
    return compuestas


def consultar_movimientos_pagina(
    session: Session,
    p: Paginacion,
    *,
    almacen_id: uuid.UUID | None = None,
    sku_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
) -> dict:
    """El kardex: qué entró y qué salió, con su rótulo.

    `movimiento_inventario` se escribía desde el primer slice y no había
    ninguna forma de leerlo: la pantalla decía cuánto queda y nunca por qué.
    """
    pagina = paginar(
        session, MovimientoRepo(session).q_list(almacen_id, sku_id, empresa_id), p
    )
    almacenes = _nombres_de_almacen(session, [m.almacen_id for m in pagina["items"]])
    skus = rotulos_de_sku(session, [m.sku_id for m in pagina["items"]])
    pagina["items"] = [
        {
            "id": m.id,
            "almacen_id": m.almacen_id,
            "almacen": almacenes.get(m.almacen_id, "(borrado)"),
            "sku_id": m.sku_id,
            "cantidad": m.cantidad,
            "tipo": m.tipo,
            "motivo_ajuste": m.motivo_ajuste,
            "lote_id": m.lote_id,
            "referencia": m.referencia,
            "usuario_id": m.usuario_id,
            "ts": m.ts,
            **skus.get(m.sku_id, {}),
        }
        for m in pagina["items"]
    ]
    return pagina


def contar_bajo_minimo(session: Session, empresa_id: uuid.UUID) -> int:
    """Cantidad de filas de stock bajo su mínimo, en almacenes de la
    empresa — para el dashboard gerencial (`core.dashboard_router`).

    Agregado en SQL (`rules.stock_bajo` es `stock_minimo is not None and
    cantidad <= stock_minimo`): antes traía toda la tabla `stock` de la
    empresa a Python para contarla ahí, en el engine corto del dashboard.
    Con el catálogo de reportes y el BI (ADR-083) sumando carga a la misma
    tabla, ese full-scan en cada apertura del dashboard dejó de ser gratis."""
    return session.scalar(
        select(func.count())
        .select_from(Stock)
        .join(Almacen, Almacen.id == Stock.almacen_id)
        .where(
            Almacen.empresa_id == empresa_id,
            Almacen.deleted_at.is_(None),
            Stock.stock_minimo.is_not(None),
            Stock.cantidad <= Stock.stock_minimo,
        )
    )
