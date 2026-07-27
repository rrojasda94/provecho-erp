"""Lectura y avance del watermark de sync (ADR-009, fase 2)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.sync.models import SyncWatermark
from src.core.sync.tiempo import a_utc, ahora

MAX_DETALLE_ERROR = 500


def _fila(session: Session, direccion: str, recurso: str) -> SyncWatermark:
    fila = session.get(SyncWatermark, (direccion, recurso))
    if fila is None:
        fila = SyncWatermark(direccion=direccion, recurso=recurso)
        session.add(fila)
        session.flush()
    return fila


def leer(session: Session, direccion: str, recurso: str) -> datetime | None:
    fila = session.get(SyncWatermark, (direccion, recurso))
    return a_utc(fila.marca) if fila else None


def registrar_ok(
    session: Session, direccion: str, recurso: str, marca: datetime | None
) -> None:
    """Avanza la marca (nunca retrocede) y limpia el último error."""
    fila = _fila(session, direccion, recurso)
    actual = a_utc(fila.marca)
    nueva = a_utc(marca)
    if nueva is not None and (actual is None or nueva > actual):
        fila.marca = nueva
    fila.ultimo_ok = ahora()
    fila.ultimo_error = None


def registrar_error(
    session: Session, direccion: str, recurso: str, detalle: str
) -> None:
    """Deja el error a la vista sin mover la marca: el recurso se reintenta
    entero en el próximo ciclo (todas las escrituras del sync son
    idempotentes, reprocesar no duplica nada)."""
    fila = _fila(session, direccion, recurso)
    fila.ultimo_error = detalle[:MAX_DETALLE_ERROR]


def resumen(session: Session) -> list[dict]:
    """Estado por recurso para `/health/sync`."""
    filas = session.scalars(
        select(SyncWatermark).order_by(SyncWatermark.direccion, SyncWatermark.recurso)
    )
    return [
        {
            "direccion": f.direccion,
            "recurso": f.recurso,
            "marca": a_utc(f.marca).isoformat() if f.marca else None,
            "ultimo_ok": a_utc(f.ultimo_ok).isoformat() if f.ultimo_ok else None,
            "ultimo_error": f.ultimo_error,
        }
        for f in filas
    ]
