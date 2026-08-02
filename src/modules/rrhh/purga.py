"""Purga de datos de postulantes vencidos (RN-PER-004, Ley 29733).

Anonimiza las fichas cuyo `plazo_conservacion_declarado` ya pasó y que no
derivaron en contratación. Corre desde el cron del host, no desde Celery
beat — mismo criterio que los backups (`docs/engineering/devops.md`).

Uso:
    python -m src.modules.rrhh.purga
"""

import sys
from datetime import UTC, datetime

from src.core.database import SessionLocal
from src.modules.rrhh.application.privacidad import purgar_postulantes_vencidos


def main() -> int:
    hoy = datetime.now(UTC).date()
    try:
        with SessionLocal() as session:
            purgados = purgar_postulantes_vencidos(session, hoy)
            session.commit()
    except Exception as e:  # noqa: BLE001 — el cron necesita ver el error
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"anonimizadas {purgados} fichas de postulante con plazo vencido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
