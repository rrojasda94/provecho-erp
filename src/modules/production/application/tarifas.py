"""Tarifa de mano de obra de producción: costo por hora-hombre (RN-PRD-018).

**Lo fija Gerencia, no el `.env`** (ADR-014/068): vive en `parametro_empresa`
y cambiarla es aprobar una propuesta, no redesplegar. `settings.production_
costo_hora_mano_obra` queda como **semilla** — el valor de arranque de una
empresa que todavía no aprobó ninguno. Mismo patrón que
`sales.application.tarifa_delivery.tarifa_de`.
"""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.shared import parametros

MODULO = "production"
CODIGO_COSTO_HORA_MANO_OBRA = "costo_hora_mano_obra"


def _decimal(valor: Any, clave: str, defecto: Decimal) -> Decimal:
    """Saca un número de lo que Gerencia aprobó, o devuelve la semilla.

    Tolerante a propósito: el valor es un JSON que pasó por un formulario y
    por la pantalla de aprobación. Un parámetro mal formado cobra la
    semilla, no tumba el cierre de la orden.
    """
    if not isinstance(valor, dict) or clave not in valor:
        return defecto
    try:
        return Decimal(str(valor[clave]))
    except (InvalidOperation, TypeError, ValueError):
        return defecto


def costo_hora_mano_obra_de(session: Session, empresa_id: uuid.UUID | None) -> Decimal:
    """Tarifa vigente de la empresa, con la semilla del `.env` de respaldo.

    Solo lee parámetros en estado `vigente`: una propuesta que Gerencia
    todavía no aprobó no cobra nada (RN-GER-009).
    """
    semilla = settings.production_costo_hora_mano_obra
    if empresa_id is None:
        return semilla
    valor = parametros.valor_vigente(session, empresa_id, MODULO, CODIGO_COSTO_HORA_MANO_OBRA)
    return _decimal(valor, "monto", semilla)
