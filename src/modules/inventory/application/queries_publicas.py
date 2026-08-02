"""Contrato público de lectura de `inventory` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `inventory`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `inventory.infrastructure` desde afuera.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models import UnidadMedida


def unidad_medida_para_magnitud(session: Session, udm_id: uuid.UUID) -> dict | None:
    """Nombre y decimales de una UdM, para expresar una cantidad con su
    unidad (RN-GER-010). `None` si no existe."""
    udm = session.scalar(select(UnidadMedida).where(UnidadMedida.id == udm_id))
    if udm is None:
        return None
    return {"id": udm.id, "nombre": udm.nombre, "decimales": udm.decimales}
