"""Casos de uso de orden de producción: crear (borrador) → registrar
consumo (en_proceso) → completar (conforme | no_conforme_reprocesado |
no_conforme_desechado).

La orden puede nacer ad-hoc o colgar de un `plan_produccion`
(`application/planes.py`); si viene de un plan, `registrar_consumo` cierra
la reserva de insumos que `planes.iniciar_plan` dejó abierta por SKU.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application import queries_publicas as inv_queries
from src.modules.inventory.application import reservas as reservas_uc
from src.modules.inventory.infrastructure.models import Articulo, Receta
from src.modules.production.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.production.domain import rules
from src.modules.production.infrastructure.models import (
    ConsumoProduccionItem,
    OrdenProduccion,
    OrdenProduccionTrabajador,
)
from src.modules.production.infrastructure.repositories import OrdenProduccionRepo
from src.modules.rrhh.application import queries_publicas as rrhh_queries
from src.modules.users.infrastructure.models import Almacen
from src.shared import auditoria, fechas


def q_ordenes(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    almacen_id: uuid.UUID | None = None,
    estado: str | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return OrdenProduccionRepo(session).q_list(empresa_id, almacen_id, estado)


def consumo_sugerido(session: Session, orden_id: uuid.UUID) -> dict:
    """Explota la receta BOM de la orden escalada a `cantidad_planeada`
    (RN-PRD-018): cuánto insumo hace falta según la ficha técnica, para
    prellenar el consumo real en vez de que la cocina lo calcule a mano."""
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    sugerido = inv_queries.consumo_sugerido_de_receta(
        session, orden.articulo_id, orden.cantidad_planeada
    )
    if sugerido is None:
        raise ReglaNegocio(f"artículo {orden.articulo_id} no tiene receta de subreceta definida")
    return sugerido


def detalle_orden(session: Session, orden_id: uuid.UUID) -> dict:
    """La orden con sus consumos reales, cada uno con la desviación de
    desperdicio (real vs. lo que la receta espera por `merma_pct`,
    RN-PRD-018) — sin esto, `peso_desperdicio_real` se guardaba y nunca se
    contrastaba contra nada."""
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    sugerido = inv_queries.consumo_sugerido_de_receta(
        session, orden.articulo_id, orden.cantidad_planeada
    )
    merma_esperada = (
        {linea["articulo_id"]: linea["merma_pct"] for linea in sugerido["items"]}
        if sugerido
        else {}
    )
    consumos = []
    for item in OrdenProduccionRepo(session).consumos(orden.id):
        merma_pct = merma_esperada.get(item.articulo_id)
        desviacion = None
        if merma_pct is not None:
            esperado = item.cantidad * merma_pct / Decimal(100)
            desviacion = item.peso_desperdicio_real - esperado
        consumos.append(
            {
                "id": item.id,
                "articulo_id": item.articulo_id,
                "cantidad": item.cantidad,
                "unidad_medida_id": item.unidad_medida_id,
                "costo_unitario": item.costo_unitario,
                "peso_desperdicio_real": item.peso_desperdicio_real,
                "tipo_desperdicio": item.tipo_desperdicio,
                "desviacion_desperdicio": desviacion,
            }
        )
    trabajadores = [
        {"trabajador_id": t.trabajador_id, "horas": t.horas}
        for t in OrdenProduccionRepo(session).trabajadores(orden.id)
    ]
    return {
        "id": orden.id,
        "articulo_id": orden.articulo_id,
        "almacen_id": orden.almacen_id,
        "plan_produccion_id": orden.plan_produccion_id,
        "origen": orden.origen,
        "cantidad_planeada": orden.cantidad_planeada,
        "cantidad_producida": orden.cantidad_producida,
        "estado": orden.estado,
        "costo_teorico_insumos": orden.costo_teorico_insumos,
        "costo_insumos": orden.costo_insumos,
        "horas_hombre": orden.horas_hombre,
        "costo_mano_obra": orden.costo_mano_obra,
        "costo_real_unitario": orden.costo_real_unitario,
        "merma_cantidad": orden.merma_cantidad,
        "merma_motivo": orden.merma_motivo,
        "evidencia_archivo_id": orden.evidencia_archivo_id,
        "fecha_vencimiento": orden.fecha_vencimiento,
        "lote_codigo": orden.lote_codigo,
        "trazabilidad": orden.trazabilidad,
        "consumos": consumos,
        "trabajadores": trabajadores,
    }


def crear_orden_produccion(
    session: Session,
    *,
    articulo_id: uuid.UUID,
    almacen_id: uuid.UUID,
    cantidad_planeada: Decimal,
    creado_por: uuid.UUID | None,
    idempotency_key: str,
    origen: str = "manual",
    ip: str | None = None,
) -> OrdenProduccion:
    """`creado_por=None` solo para `origen="ajuste_por_necesidad"`: la crea
    el listener de `inventory.stock_bajo_minimo` sin ningún humano detrás
    (RN-PRD-007) — la API siempre manda el `actor.id` de quien la pide."""
    repo = OrdenProduccionRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    articulo = session.get(Articulo, articulo_id)
    if articulo is None:
        raise NoEncontrado(f"artículo {articulo_id} no encontrado")
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        raise NoEncontrado(f"almacén {almacen_id} no encontrado")
    if Decimal(str(cantidad_planeada)) <= 0:
        raise ReglaNegocio("cantidad_planeada debe ser > 0")
    if session.scalar(select(Receta).where(Receta.articulo_id == articulo_id)) is None:
        raise ReglaNegocio(f"artículo {articulo_id} no tiene receta de subreceta definida")

    orden = repo.add(
        OrdenProduccion(
            articulo_id=articulo_id,
            almacen_id=almacen_id,
            cantidad_planeada=Decimal(str(cantidad_planeada)),
            estado="borrador",
            origen=origen,
            creado_por=creado_por,
            idempotency_key=idempotency_key,
        )
    )
    # Acto de autoridad: abre el consumo de insumos de una orden nueva
    # (ADR-031) — quién la creó, con qué artículo/almacén/cantidad.
    auditoria.registrar(
        session,
        usuario_id=creado_por,
        entidad="orden_produccion",
        accion="crear",
        entidad_id=orden.id,
        datos_despues={
            "articulo_id": str(articulo_id),
            "almacen_id": str(almacen_id),
            "cantidad_planeada": str(orden.cantidad_planeada),
        },
        empresa_id=almacen.empresa_id,
        ip=ip,
    )
    return orden


def _registrar_item_consumo(session: Session, orden: OrdenProduccion, it: dict) -> dict:
    """Guarda un ítem de `ConsumoProduccionItem` y devuelve su forma para el
    evento. Extraído de `registrar_consumo` para no repetir la conversión
    de UdM (RN-UDM-005) y el costeo por defecto (RN-PRD-018) en cada línea."""
    articulo = session.get(Articulo, it["articulo_id"])
    if articulo is None:
        raise NoEncontrado(f"artículo {it['articulo_id']} no encontrado")
    cantidad = Decimal(str(it["cantidad"]))
    unidad_medida_id = it.get("unidad_medida_id")
    # RN-UDM-005: se puede teclear en otra UdM de la misma categoría (los
    # gramos que el cocinero tiene a mano); se guarda ya convertida a la
    # del artículo, que es la que `costo_insumos` y el stock necesitan.
    if unidad_medida_id is not None and unidad_medida_id != articulo.unidad_medida_id:
        convertida = inv_queries.convertir_a_udm_de_articulo(
            session, it["articulo_id"], cantidad, unidad_medida_id
        )
        if convertida is None:
            raise ReglaNegocio(
                "la unidad de medida del ítem no es de la misma categoría "
                "que la del artículo"
            )
        cantidad = convertida
    else:
        unidad_medida_id = None
    if cantidad <= 0:
        raise ReglaNegocio("cantidad de consumo debe ser > 0")
    # Sin costo_unitario explícito, se costea al costo_promedio vigente del
    # artículo (RN-PRD-018): antes lo tipeaba siempre quien registraba el
    # consumo, sin ninguna referencia contra la que contrastarlo.
    costo_unitario = it.get("costo_unitario")
    costo_unitario = (
        Decimal(str(costo_unitario)) if costo_unitario is not None else articulo.costo_promedio
    )
    session.add(
        ConsumoProduccionItem(
            orden_produccion_id=orden.id,
            articulo_id=it["articulo_id"],
            cantidad=cantidad,
            unidad_medida_id=unidad_medida_id,
            costo_unitario=costo_unitario,
            peso_desperdicio_real=Decimal(str(it.get("peso_desperdicio_real", 0))),
            tipo_desperdicio=it.get("tipo_desperdicio"),
        )
    )
    return {
        "articulo_id": str(it["articulo_id"]),
        "cantidad": str(cantidad),
        "costo_unitario": str(costo_unitario),
    }


def _consumir_reservas_del_plan(
    session: Session, orden: OrdenProduccion, items: list[dict]
) -> None:
    """La reserva que `planes.iniciar_plan` dejó abierta por SKU se cierra
    acá: el insumo ya salió de verdad, y dejarla activa descontaría el
    disponible dos veces (una por la reserva, otra por el movimiento real
    que dispara `production.consumo_registrado`)."""
    for sku_id in {inv_queries.sku_de_articulo(session, it["articulo_id"]) for it in items}:
        if sku_id is not None:
            reservas_uc.consumir_por_referencia(session, orden.id, sku_id)


def registrar_consumo(
    session: Session,
    orden_id: uuid.UUID,
    *,
    # [{articulo_id, cantidad, costo_unitario?, unidad_medida_id?,
    #   peso_desperdicio_real, tipo_desperdicio}]
    items: list[dict],
    actor_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    ip: str | None = None,
) -> OrdenProduccion:
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    # Reintento de red con la misma clave: la orden ya quedó en_proceso con
    # este consumo, no se vuelve a procesar (evita duplicar filas/stock).
    if idempotency_key is not None and orden.consumo_idempotency_key == idempotency_key:
        return orden
    if not rules.puede_registrar_consumo(orden.estado):
        raise Conflicto(f"la orden está {orden.estado}; no admite registrar consumo")
    if not items:
        raise ReglaNegocio("una orden requiere al menos un ítem de consumo")

    evento_items = [_registrar_item_consumo(session, orden, it) for it in items]

    if orden.plan_produccion_id is not None:
        _consumir_reservas_del_plan(session, orden, items)

    # Snapshot de lo que la receta BOM dice que debería costar, para comparar
    # contra `costo_insumos` (lo real) al completar (RN-PRD-018). `None` si el
    # artículo no tiene receta que lo produzca: no hay contra qué comparar.
    sugerido = inv_queries.consumo_sugerido_de_receta(
        session, orden.articulo_id, orden.cantidad_planeada
    )
    # Cuantizado a la escala de la columna (Numeric(12, 4)): sin esto, el
    # valor recién calculado en memoria y el que vuelve de releer la fila
    # difieren en cómo Decimal representa el mismo número (`0E-10` vs
    # `0.0000`), y un reintento idempotente dejaba de ser byte a byte igual
    # al original.
    orden.costo_teorico_insumos = (
        sugerido["costo_total"].quantize(Decimal("0.0001")) if sugerido else None
    )

    estado_previo = orden.estado
    orden.estado = "en_proceso"
    orden.consumo_idempotency_key = idempotency_key
    session.flush()
    almacen = session.get(Almacen, orden.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="orden_produccion",
        accion="registrar_consumo",
        entidad_id=orden.id,
        datos_antes={"estado": estado_previo},
        datos_despues={"estado": "en_proceso", "items": evento_items},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    event_bus.publish(
        "production.consumo_registrado",
        {
            "orden_produccion_id": str(orden.id),
            "almacen_id": str(orden.almacen_id),
            "items": evento_items,
        },
        session=session,
    )
    return orden


def _cerrar_conforme(
    session: Session,
    orden: OrdenProduccion,
    *,
    cantidad_producida: Decimal | None,
    costo_insumos: Decimal,
    costo_mano_obra: Decimal,
    fecha_vencimiento: date | None,
    lote_codigo: str | None,
) -> dict:
    """Cierra en conforme: fija costo real, y si hay vencimiento/lote los
    manda en el evento para que el lote del producto terminado nazca con
    ellos (RN-VNC-001) — el listener de `inventory` ya los sabe leer."""
    if not cantidad_producida or Decimal(str(cantidad_producida)) <= 0:
        raise ReglaNegocio("resultado 'conforme' requiere cantidad_producida > 0")
    cantidad_producida = Decimal(str(cantidad_producida))
    orden.cantidad_producida = cantidad_producida
    orden.costo_real_unitario = rules.costo_real_unitario(
        costo_insumos, costo_mano_obra, cantidad_producida
    )
    orden.estado = "conforme"
    if fecha_vencimiento:
        orden.fecha_vencimiento = fecha_vencimiento
    if lote_codigo:
        orden.lote_codigo = lote_codigo

    payload = {
        "orden_produccion_id": str(orden.id),
        "almacen_id": str(orden.almacen_id),
        "articulo_id": str(orden.articulo_id),
        "cantidad_producida": str(cantidad_producida),
        "costo_unitario": str(orden.costo_real_unitario),
    }
    if orden.fecha_vencimiento:
        payload["fecha_vencimiento"] = orden.fecha_vencimiento.isoformat()
    if orden.lote_codigo:
        payload["lote_codigo"] = orden.lote_codigo
    event_bus.publish("production.orden_completada", payload, session=session)
    return {"costo_real_unitario": str(orden.costo_real_unitario)}


def _cerrar_no_conforme(
    session: Session,
    orden: OrdenProduccion,
    *,
    resultado: str,
    costo_insumos: Decimal,
    merma_cantidad: Decimal | None,
    merma_motivo: str | None,
    registrado_por: uuid.UUID | None,
) -> dict:
    """Reproceso no genera merma ni asiento (RN-PRD); desecho exige que ya
    se haya adjuntado evidencia de destrucción (RN-PRD-015, `POST
    /ordenes/{id}/evidencia` — `orden.evidencia_archivo_id`) antes de
    aceptar la merma, y dispara el asiento contable por el costo de insumos
    ya consumidos (ADR-098 — no se reusa `inventory.merma_registrada`: el
    producto terminado de una orden desechada nunca llegó a existir como
    stock)."""
    extra: dict = {}
    if resultado == "no_conforme_desechado":
        if not merma_cantidad or Decimal(str(merma_cantidad)) <= 0:
            raise ReglaNegocio("desecho requiere merma_cantidad > 0")
        if not merma_motivo:
            raise ReglaNegocio("desecho requiere merma_motivo")
        if orden.evidencia_archivo_id is None:
            raise ReglaNegocio(
                "desecho requiere evidencia de destrucción adjunta primero "
                "(POST /ordenes/{id}/evidencia, RN-PRD-015)"
            )
        orden.merma_cantidad = Decimal(str(merma_cantidad))
        orden.merma_motivo = merma_motivo
        extra["merma_cantidad"] = str(orden.merma_cantidad)
    orden.estado = resultado
    event_bus.publish(
        "production.no_conformidad_detectada",
        # `almacen_id` desde 2026-08-08: es de donde `reports` deduce la
        # empresa y la sucursal del hecho para escopar y distribuir el
        # reporte. Sin él la emisión no se puede atribuir a un tenant.
        {
            "orden_produccion_id": str(orden.id),
            "almacen_id": str(orden.almacen_id),
            "resultado": resultado,
            # Quien cerró la orden con el control de calidad en la mano:
            # es a quien Gerencia le va a preguntar qué pasó.
            "registrado_por": str(registrado_por) if registrado_por else None,
            # Para que el `reporte_escalamiento` nazca con la misma
            # evidencia (RN-PRD-015) — antes había dos mecanismos para lo
            # mismo y ninguno llenaba al otro.
            "evidencia_id": (
                str(orden.evidencia_archivo_id) if orden.evidencia_archivo_id else None
            ),
        },
        session=session,
    )
    if resultado == "no_conforme_desechado":
        # Un solo asiento contable posible por hallazgo (política del área):
        # el reproceso no llega hasta acá, ya volvió arriba.
        event_bus.publish(
            "production.orden_desechada",
            {
                "orden_produccion_id": str(orden.id),
                "almacen_id": str(orden.almacen_id),
                "articulo_id": str(orden.articulo_id),
                "merma_cantidad": str(orden.merma_cantidad),
                "merma_motivo": orden.merma_motivo,
                "monto": str(costo_insumos),
                "registrado_por": str(registrado_por) if registrado_por else None,
            },
            session=session,
        )
    return extra


def _horas_hombre_de_trabajadores(
    session: Session, orden: OrdenProduccion, trabajadores: list[dict]
) -> Decimal:
    """Reemplaza el `horas_hombre` tipeado a mano: cada trabajador imputado
    aporta lo que de verdad asistió hoy (RN-RRHH-022, vía `rrhh.
    queries_publicas.horas_asistidas`), tope su propia asistencia — no se
    puede imputar más horas de las que marcó — y sin asistencia ese día no
    se puede imputar nada (RN-RRHH-009: lo que no se marcó no cuenta).
    `horas_hombre = Σ horas` es lo único que sigue viviendo en la orden."""
    if not trabajadores:
        return Decimal(0)
    trabajador_ids = [t["trabajador_id"] for t in trabajadores]
    asistidas = rrhh_queries.horas_asistidas(session, trabajador_ids, fechas.hoy())
    total = Decimal(0)
    for t in trabajadores:
        trabajador_id = t["trabajador_id"]
        asistida = asistidas.get(trabajador_id)
        if asistida is None:
            raise ReglaNegocio(
                f"el trabajador {trabajador_id} no tiene asistencia registrada "
                "hoy (RN-RRHH-009)"
            )
        horas = Decimal(str(t["horas"])) if t.get("horas") is not None else asistida
        if horas <= 0:
            raise ReglaNegocio("las horas imputadas deben ser > 0")
        if horas > asistida:
            raise ReglaNegocio(
                f"el trabajador {trabajador_id} solo asistió {asistida} horas "
                f"hoy: no se le puede imputar {horas}"
            )
        session.add(
            OrdenProduccionTrabajador(
                orden_produccion_id=orden.id, trabajador_id=trabajador_id, horas=horas
            )
        )
        total += horas
    return total


def completar_orden_produccion(
    session: Session,
    orden_id: uuid.UUID,
    *,
    resultado: str,
    costo_hora_mano_obra: Decimal,
    cantidad_producida: Decimal | None = None,
    trabajadores: list[dict] | None = None,
    merma_cantidad: Decimal | None = None,
    merma_motivo: str | None = None,
    fecha_vencimiento: date | None = None,
    lote_codigo: str | None = None,
    trazabilidad: dict | None = None,
    registrado_por: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    ip: str | None = None,
) -> OrdenProduccion:
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    # Reintento de red con la misma clave: la orden ya quedó cerrada con
    # este resultado, no se vuelve a cerrar (evita duplicar el asiento/lote).
    if idempotency_key is not None and orden.cierre_idempotency_key == idempotency_key:
        return orden
    if not rules.puede_completar(orden.estado):
        raise Conflicto(f"la orden está {orden.estado}; no admite completarse")
    if resultado not in rules.RESULTADOS_CONTROL_CALIDAD:
        raise ReglaNegocio(f"resultado de control de calidad inválido: {resultado}")

    costo_insumos = sum(
        (c.cantidad * c.costo_unitario for c in OrdenProduccionRepo(session).consumos(orden.id)),
        Decimal(0),
    )
    horas_hombre = _horas_hombre_de_trabajadores(session, orden, trabajadores or [])
    costo_mano_obra = horas_hombre * costo_hora_mano_obra
    estado_previo = orden.estado
    orden.horas_hombre = horas_hombre
    orden.costo_insumos = costo_insumos
    orden.costo_mano_obra = costo_mano_obra
    orden.cierre_idempotency_key = idempotency_key
    if trazabilidad is not None:
        orden.trazabilidad = trazabilidad

    if resultado == "conforme":
        extra = _cerrar_conforme(
            session,
            orden,
            cantidad_producida=cantidad_producida,
            costo_insumos=costo_insumos,
            costo_mano_obra=costo_mano_obra,
            fecha_vencimiento=fecha_vencimiento,
            lote_codigo=lote_codigo,
        )
    else:
        extra = _cerrar_no_conforme(
            session,
            orden,
            resultado=resultado,
            costo_insumos=costo_insumos,
            merma_cantidad=merma_cantidad,
            merma_motivo=merma_motivo,
            registrado_por=registrado_por,
        )

    session.flush()
    almacen = session.get(Almacen, orden.almacen_id)
    # Acto de autoridad y de plata por definición: cierra el control de
    # calidad, fija el costo real y, en el desecho, declara la merma
    # (ADR-031) — sin esto no quedaba registrado quién hizo cada paso, que
    # es justo lo que compensa no exigir aprobador≠solicitante acá (ver
    # ROADMAP: decisión de no segregar crear/completar).
    auditoria.registrar(
        session,
        usuario_id=registrado_por,
        entidad="orden_produccion",
        accion="completar",
        entidad_id=orden.id,
        datos_antes={"estado": estado_previo},
        datos_despues={"estado": resultado, **extra},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    return orden
