"""Smoke test del esquema: mappers válidos, tablas esperadas, FKs resolubles."""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.infrastructure.models import Empresa, Grupo

TABLAS_ESPERADAS = {
    "persona",
    "grupo",
    "empresa",
    "marca",
    "licencia_marca",
    "sucursal",
    "almacen",
    "categoria",
    "categoria_udm",
    "unidad_medida",
    "archivo",
}


def test_metadata_contiene_tablas_esperadas():
    assert TABLAS_ESPERADAS <= set(Base.metadata.tables)


def test_mappers_configuran_sin_errores():
    configure_mappers()


def test_esquema_se_crea_e_inserta():
    # SQLite en memoria: valida DDL portable, defaults y FKs sin Postgres.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        grupo = Grupo(nombre="Grupo Majambo")
        session.add(grupo)
        session.flush()
        empresa = Empresa(
            grupo_id=grupo.id,
            razon_social="Inversiones Turísticas y Alimentarias Majambo EIRL",
            ruc="20450311520",
            domicilio_fiscal="Tarapoto, San Martín",
            tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        )
        session.add(empresa)
        session.commit()
        assert isinstance(empresa.id, uuid.UUID)
        assert empresa.created_at is not None
