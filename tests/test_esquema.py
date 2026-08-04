"""Deriva de esquema (`src/core/esquema.py`).

El caso que motivó el chequeo: `alembic_version` marcando una revisión
posterior a la que crea una tabla, con la tabla ausente. Alembic decía "al
día", el endpoint respondía 500 y nada en el sistema lo notaba.
"""

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, text

from src.core.esquema import diagnosticar, head_del_repo, verificar_al_arrancar


def _metadata_con(*nombres: str) -> MetaData:
    metadata = MetaData()
    for nombre in nombres:
        Table(nombre, metadata, Column("id", Integer, primary_key=True))
    return metadata


@pytest.fixture()
def engine():
    return create_engine("sqlite://")


def _marcar_revision(engine, revision: str) -> None:
    with engine.begin() as c:
        c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        c.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})


def test_base_al_dia_no_reporta_deriva(engine):
    metadata = _metadata_con("uno", "dos")
    metadata.create_all(engine)
    _marcar_revision(engine, head_del_repo() or "sin-head")

    diagnostico = diagnosticar(engine, metadata)
    assert diagnostico.tablas_faltantes == ()
    assert not diagnostico.hay_deriva
    assert diagnostico.resumen() == "esquema al día"


def test_tabla_ausente_se_detecta_aunque_la_revision_sea_la_correcta(engine):
    """El fallo real: la marca dice que la migración corrió y la tabla no
    está. Mirar solo `alembic_version` no lo habría visto."""
    metadata = _metadata_con("uno", "dos")
    metadata.tables["uno"].create(engine)  # "dos" nunca se crea
    _marcar_revision(engine, head_del_repo() or "sin-head")

    diagnostico = diagnosticar(engine, metadata)
    assert diagnostico.tablas_faltantes == ("dos",)
    assert diagnostico.hay_deriva
    assert "dos" in diagnostico.resumen()


def test_revision_atrasada_se_detecta_aunque_no_falte_ninguna_tabla(engine):
    """Una migración que solo agrega columnas o índices no se nota en la
    lista de tablas: para eso está la comparación de revisión."""
    metadata = _metadata_con("uno")
    metadata.create_all(engine)
    _marcar_revision(engine, "revision-vieja")

    diagnostico = diagnosticar(engine, metadata)
    assert diagnostico.tablas_faltantes == ()
    assert diagnostico.revision_desalineada
    assert "alembic upgrade head" in diagnostico.resumen()


def test_sin_alembic_version_no_se_afirma_nada_de_la_revision(engine):
    """Base virgen o sin permisos sobre la tabla: se avisa, pero no se
    inventa una desalineación que no se pudo comprobar."""
    metadata = _metadata_con("uno")
    metadata.create_all(engine)

    diagnostico = diagnosticar(engine, metadata)
    assert diagnostico.revision_bd is None
    assert not diagnostico.revision_desalineada
    assert diagnostico.alertas


def test_el_repo_tiene_una_sola_cabeza():
    """Dos cabezas = rama sin mergear; el chequeo no podría decidir qué
    revisión esperar."""
    assert head_del_repo() is not None


# --- El guard de arranque ----------------------------------------------------
def test_en_produccion_la_deriva_aborta_el_arranque(engine):
    metadata = _metadata_con("uno", "dos")
    metadata.tables["uno"].create(engine)

    with pytest.raises(RuntimeError, match="Deriva de esquema"):
        verificar_al_arrancar(engine, metadata, estricto=True)


def test_en_desarrollo_la_deriva_solo_avisa(engine, caplog):
    metadata = _metadata_con("uno", "dos")
    metadata.tables["uno"].create(engine)

    with caplog.at_level("WARNING"):
        diagnostico = verificar_al_arrancar(engine, metadata, estricto=False)

    assert diagnostico.hay_deriva
    assert "Deriva de esquema" in caplog.text


def test_sin_deriva_el_arranque_estricto_pasa(engine):
    metadata = _metadata_con("uno")
    metadata.create_all(engine)
    _marcar_revision(engine, head_del_repo())

    assert not verificar_al_arrancar(engine, metadata, estricto=True).hay_deriva
