"""Avisos de sonido/toast para KDS y caja (ADR-101): qué entrega se
registró y qué ruta terminó después de `desde`. Es polling barato sobre lo
que ya se guarda —sin push, deuda ya declarada en
`docs/roadmap/deuda/modulo-delivery.md`— y sin datos del cliente: solo lo
que una pantalla necesita para una línea de aviso.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RutaRepo
from src.modules.rrhh.application.queries_publicas import cuenta_de_trabajador
from src.modules.sales.application.queries_publicas import venta_para_reparto


def _nombre_repartidor(session: Session, repartidor_id: uuid.UUID | None) -> str | None:
    if repartidor_id is None:
        return None
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None:
        return None
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    return cuenta["nombre"] if cuenta else None


def _aviso_de_entrega(session: Session, entrega: Entrega) -> dict:
    venta = venta_para_reparto(session, entrega.venta_id)
    return {
        "entrega_id": entrega.id,
        "numero_orden": venta["numero_orden"] if venta else None,
        "repartidor_nombre": _nombre_repartidor(session, entrega.repartidor_id),
        # Solo si la venta sigue `orden` (sin pagar) — mismo criterio que
        # `mi_reparto._parada_de`: es lo que caja tiene que cobrar en la
        # puerta o al repartidor, no un dato ya irrelevante si se pagó.
        "monto_a_cobrar": venta["total"] if venta and venta["estado"] == "orden" else None,
        "fecha_entrega": entrega.fecha_entrega,
    }


def _aviso_de_ruta(session: Session, ruta: RutaReparto, entregas_repo: EntregaRepo) -> dict:
    estados = [e.estado for e in entregas_repo.de_ruta(ruta.id)]
    return {
        "ruta_id": ruta.id,
        "repartidor_nombre": _nombre_repartidor(session, ruta.repartidor_id),
        "entregadas": sum(1 for e in estados if e == "entregada"),
        "fallidas": sum(1 for e in estados if e == "fallida"),
        "hora_fin": ruta.hora_fin,
    }


def avisos_desde(session: Session, sucursal_ids: Sequence[uuid.UUID], desde: datetime) -> dict:
    """`{entregas, rutas_finalizadas}` desde `desde` — el cliente sondea
    esto cada tantos segundos y dispara un toast/beep por cada fila nueva."""
    entrega_repo = EntregaRepo(session)
    entregas = [
        _aviso_de_entrega(session, e) for e in entrega_repo.entregadas_desde(sucursal_ids, desde)
    ]
    rutas = [
        _aviso_de_ruta(session, r, entrega_repo)
        for r in RutaRepo(session).finalizadas_desde(sucursal_ids, desde)
    ]
    return {"ahora": datetime.now(UTC), "entregas": entregas, "rutas_finalizadas": rutas}
