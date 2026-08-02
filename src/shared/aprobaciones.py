"""Lectura de umbrales de aprobación como `Decimal`.

Envoltorio tipado sobre `parametro_empresa` (ADR-014) para los módulos que
comparan un monto contra un umbral: el valor se guarda como
`{"monto": "2000.00"}` y acá vuelve como `Decimal`. Único punto que los
módulos operativos deben consultar en vez de hardcodear su propio umbral
(RN-GER-003).

Reemplaza a la tabla `regla_aprobacion`, retirada el 2026-08-02 (migración
`b82d4c1f7a35`): un umbral es un parámetro operativo más y pasa por el mismo
flujo de aprobación de Gerencia que el resto (RN-GER-009).
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from src.shared import parametros


def umbral_vigente(
    session: Session,
    empresa_id: uuid.UUID,
    modulo: str,
    codigo: str,
    default: Decimal,
) -> Decimal:
    """Umbral aprobado para `empresa_id`/`modulo`/`codigo`, o `default`
    (valor semilla del propio módulo) si Gerencia no aprobó ninguno."""
    valor = parametros.valor_vigente(session, empresa_id, modulo, codigo)
    monto = valor.get("monto") if isinstance(valor, dict) else valor
    return default if monto is None else Decimal(str(monto))
