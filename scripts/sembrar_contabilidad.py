"""Le siembra el plan de cuentas a las empresas que se crearon sin él.

Desde ADR-089 una empresa nace con su PCGE —`accounting` escucha
`organizacion.empresa_creada`— pero las que ya existían quedaron sin cuentas,
y sin cuentas **ningún asiento automático entra**: la venta se registra, el
stock se mueve, y el balance sigue vacío. Este script es el backfill de una
sola vez.

No abre periodos: desde ADR-089 el periodo se abre solo al primer asiento del
mes, así que basta con que las cuentas existan.

Tampoco repone los asientos que se perdieron. Eso es otro problema —hay que
saber qué eventos hubo, no solo qué cuentas faltan— y va en su propia rama.

Uso:

    python scripts/sembrar_contabilidad.py            # todas las empresas
    python scripts/sembrar_contabilidad.py --dry-run  # solo dice qué haría
"""

import argparse

from sqlalchemy import select

import src.core.models_registry  # noqa: F401
from src.core.database import SessionLocal
from src.modules.accounting.application.pcge import importar_pcge
from src.modules.users.infrastructure.models import Empresa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="no escribe, solo informa"
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        empresas = list(session.scalars(select(Empresa)))
        if not empresas:
            print("No hay empresas.")
            return 0
        for empresa in empresas:
            if args.dry_run:
                print(f"{empresa.razon_social}: se le importaría el PCGE")
                continue
            resultado = importar_pcge(session, empresa_id=empresa.id)
            print(
                f"{empresa.razon_social}: {resultado['creadas']} cuentas creadas, "
                f"{resultado['existentes']} ya estaban"
            )
        if not args.dry_run:
            session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
