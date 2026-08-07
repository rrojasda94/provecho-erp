"""Margen de error tolerado al ajustar stock, resuelto por empresa (ADR-014).

Lo usan los dos productores de ajustes —el cierre de conteo y el ajuste
ad-hoc— y ninguno de los dos debe recibirlo del cliente: `dentro_margen`
es lo que decide si la diferencia dispara `inventory.ajuste_fuera_margen`,
y un control que el controlado declara no es un control.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.inventory.infrastructure.models import Articulo, Sku
from src.shared.parametros import valor_vigente

# Código del parámetro operativo que Gerencia aprueba por empresa.
MARGEN_AJUSTE = "margen_error_ajuste"


def margen_de_empresa(
    session: Session, empresa_id: uuid.UUID
) -> tuple[Decimal, Decimal | None]:
    """Porcentaje y piso en dinero vigentes para esta empresa.

    El valor de `settings` deja de ser la regla y pasa a ser el default de
    arranque: rige hasta que Gerencia apruebe el suyo. Sin piso aprobado el
    piso no existe (`None`), no es cero — cero significaría "ninguna
    diferencia se tolera por monto", que no es lo mismo que "no configurado".
    """
    valor = valor_vigente(session, empresa_id, "inventory", MARGEN_AJUSTE)
    if not isinstance(valor, dict):
        return settings.inventory_margen_ajuste_pct, None
    pct = valor.get("porcentaje", settings.inventory_margen_ajuste_pct)
    piso = valor.get("piso")
    return Decimal(str(pct)), None if piso is None else Decimal(str(piso))


def costos_por_sku(
    session: Session, sku_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    """Costo promedio del artículo de cada SKU, para valorizar la diferencia
    contra el piso. Un SKU sin fila deja el costo en 0 y la valorización en
    0, que cae dentro del piso: sin costo no hay monto que investigar."""
    if not sku_ids:
        return {}
    filas = session.execute(
        select(Sku.id, Articulo.costo_promedio)
        .join(Articulo, Articulo.id == Sku.articulo_id)
        .where(Sku.id.in_(sku_ids))
    ).all()
    return {sku_id: costo for sku_id, costo in filas}
