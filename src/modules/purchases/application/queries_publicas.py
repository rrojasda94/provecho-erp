"""Contrato público de lectura de `purchases` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `purchases`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `purchases.infrastructure` desde
afuera.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.purchases.infrastructure.models import OrdenCompra, Proveedor
from src.modules.users.infrastructure.models import Persona
from src.shared import fechas

# Una OC en borrador todavía no es compra: no se le pidió nada a nadie.
# Una anulada dejó de serlo. Ninguna de las dos cuenta como gasto.
_ESTADOS_CON_COMPROMISO = ("emitida", "recibida_parcial", "recibida")


def compras_por_proveedor(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
    estados: Sequence[str] | None = None,
    limite: int = 20,
) -> list[dict]:
    """Cuánto se le compró a cada proveedor en el rango, para el tablero de
    gerencia y la negociación por volumen.

    Filtra por `created_at` convertido a la zona del negocio (`fechas`): la
    base guarda el instante en UTC y una OC emitida a las 20:00 hora Perú
    es de ese día, no del siguiente.
    """
    nombre = func.coalesce(
        Proveedor.razon_social,
        Persona.nombres + " " + Persona.apellidos,
    )
    stmt = (
        select(
            Proveedor.id,
            nombre.label("proveedor"),
            func.count(OrdenCompra.id),
            func.coalesce(func.sum(OrdenCompra.total), 0),
        )
        .select_from(OrdenCompra)
        .join(Proveedor, Proveedor.id == OrdenCompra.proveedor_id)
        .outerjoin(Persona, Persona.id == Proveedor.persona_id)
        .where(
            OrdenCompra.estado.in_(list(estados or _ESTADOS_CON_COMPROMISO)),
            OrdenCompra.created_at >= fechas.inicio_dia_utc(desde),
            OrdenCompra.created_at <= fechas.fin_dia_utc(hasta),
        )
        .group_by(Proveedor.id, nombre)
        .order_by(func.coalesce(func.sum(OrdenCompra.total), 0).desc())
        .limit(limite)
    )
    if empresa_id is not None:
        stmt = stmt.where(Proveedor.empresa_id == empresa_id)

    return [
        {
            "proveedor_id": proveedor_id,
            "proveedor": proveedor,
            "cantidad": cantidad,
            "total": Decimal(total),
        }
        for proveedor_id, proveedor, cantidad, total in session.execute(stmt)
    ]
