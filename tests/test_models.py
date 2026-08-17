"""Smoke test del esquema: mappers válidos, tablas esperadas, FKs resolubles."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
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


def test_un_engine_sqlite_nuevo_ya_trae_las_fk_encendidas():
    """El seguro del suite entero, en un test.

    SQLite trae las FK apagadas; el listener de `tests/conftest.py` las
    enciende en cualquier engine del proceso. Si alguien lo saca, ~75 fixtures
    vuelven a dejar pasar en verde lo que Postgres rechaza —y nada más se
    pondría rojo—, así que el guardián necesita su propio test.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
        session.add(
            Empresa(
                grupo_id=uuid.uuid4(),
                razon_social="Empresa sin grupo",
                ruc="20450311520",
                domicilio_fiscal="Tarapoto",
                tipo="operativa",
                zona_tributaria="amazonia_ley27037",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
