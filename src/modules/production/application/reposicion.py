"""Factor de reposición por necesidad (RN-PRD-007/011): cuánto de más sobre
`stock_minimo` pide la orden que `application/listeners.py` crea sola al
cruzar `inventory.stock_bajo_minimo` — para no volver a cruzarlo la semana
siguiente con el lote justo.

**Lo fija Gerencia** (ADR-014/068): vive en `parametro_empresa`, mismo
patrón que `sales.application.tarifa_delivery` y `production.application.
tarifas`. Sin propuesta aprobada, la semilla es `2` (el doble del mínimo) —
no hay valor de `.env` que la respalde porque no es un número de dominio
externo, es una política de reposición interna.
"""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from src.shared import parametros

MODULO = "production"
CODIGO_FACTOR_REPOSICION = "factor_reposicion"
FACTOR_SEMILLA = Decimal("2")


def _decimal(valor: Any, clave: str, defecto: Decimal) -> Decimal:
    if not isinstance(valor, dict) or clave not in valor:
        return defecto
    try:
        return Decimal(str(valor[clave]))
    except (InvalidOperation, TypeError, ValueError):
        return defecto


def factor_reposicion_de(session: Session, empresa_id: uuid.UUID | None) -> Decimal:
    """Factor vigente de la empresa, con `2` de semilla mientras Gerencia no
    apruebe una propuesta (RN-GER-009)."""
    if empresa_id is None:
        return FACTOR_SEMILLA
    valor = parametros.valor_vigente(session, empresa_id, MODULO, CODIGO_FACTOR_REPOSICION)
    return _decimal(valor, "factor", FACTOR_SEMILLA)
