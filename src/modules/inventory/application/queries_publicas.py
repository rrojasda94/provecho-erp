"""Contrato público de lectura de `inventory` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para que otro módulo lea datos de `inventory`, devolviendo DTOs
(dicts), nunca el ORM. Nadie importa `inventory.infrastructure` desde afuera.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models import Receta, UnidadMedida


def unidad_medida_para_magnitud(session: Session, udm_id: uuid.UUID) -> dict | None:
    """Nombre y decimales de una UdM, para expresar una cantidad con su
    unidad (RN-GER-010). `None` si no existe."""
    udm = session.scalar(select(UnidadMedida).where(UnidadMedida.id == udm_id))
    if udm is None:
        return None
    return {"id": udm.id, "nombre": udm.nombre, "decimales": udm.decimales}


def receta_resumen(session: Session, receta_id: uuid.UUID) -> dict | None:
    """Nombre y rendimiento de una receta, para que `sales` valide que la
    que le asignan a un producto comercial existe sin importar su ORM.
    `None` si no existe."""
    receta = session.scalar(select(Receta).where(Receta.id == receta_id))
    if receta is None:
        return None
    return {
        "id": receta.id,
        "nombre": receta.nombre,
        "rendimiento_cantidad": receta.rendimiento_cantidad,
        "rendimiento_unidad_medida_id": receta.rendimiento_unidad_medida_id,
        "articulo_id": receta.articulo_id,
    }
