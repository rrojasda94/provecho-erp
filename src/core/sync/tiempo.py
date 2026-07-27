"""Normalización de marcas de tiempo del sync (ADR-009, fase 2).

El watermark compara `updated_at` contra un valor que viene del otro lado
del cable, así que la conciencia de zona horaria no puede quedar librada
al dialecto: Postgres devuelve datetimes *aware*, SQLite (tests) *naive*.
Todo el motor trabaja en UTC aware y solo al bindear una consulta se
adapta al dialecto que la va a ejecutar.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

# SQLite guarda `CURRENT_TIMESTAMP` sin microsegundos ('...:16') pero
# bindea los datetime de Python con ellos ('...:16.000000'), y compara los
# dos como texto: una fila escrita en el MISMO segundo que el watermark
# quedaría fuera de un `>=`. Se ensancha el borde un segundo — como todo el
# sync es idempotente, reprocesar un puñado de filas no cuesta nada, y
# perderlas sí. En Postgres (nube y hub reales) no aplica.
_HOLGURA_SQLITE = timedelta(seconds=1)


def a_utc(dt: datetime | None) -> datetime | None:
    """Naive → UTC aware (los naive que guardamos siempre son UTC)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def para_dialecto(session: Session, dt: datetime | None) -> datetime | None:
    """Valor comparable contra lo que ESA base tiene guardado."""
    if dt is None:
        return None
    dt = a_utc(dt)
    motor = session.get_bind()
    if motor is not None and motor.dialect.name == "sqlite":
        return dt.replace(tzinfo=None) - _HOLGURA_SQLITE
    return dt


def ahora() -> datetime:
    return datetime.now(UTC)
