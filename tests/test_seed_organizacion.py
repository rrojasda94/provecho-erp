"""El seeder deja montada la organización real del Grupo Majambo.

Contra SQLite en memoria: valida los datos sembrados y la idempotencia
(correrlo dos veces no duplica ni reescribe nada).
"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    LicenciaMarca,
    Marca,
    Permiso,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.seeders.seed import USUARIOS_SEMILLA, seed
from src.shared.parametros import MODULOS

SEDE_CASTILLA = "Jr. Ramón Castilla 248 - Tarapoto"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def sembrado(session):
    seed(session)
    return session


def test_empresa_con_ruc_domicilio_y_zona_amazonica(sembrado):
    empresa = sembrado.scalar(select(Empresa).where(Empresa.ruc == "20450311520"))
    assert empresa is not None
    assert empresa.razon_social == "Inversiones Turísticas y Alimentarias Majambo EIRL"
    assert empresa.domicilio_fiscal == SEDE_CASTILLA
    assert empresa.tipo == "operativa"
    # Tarapoto está en zona de Amazonía: exoneración de IGV (RN-IMP-001).
    assert empresa.zona_tributaria == "amazonia_ley27037"
    assert empresa.grupo_id == sembrado.scalar(select(Grupo.id))


def test_marca_licenciada_a_la_empresa(sembrado):
    marca = sembrado.scalar(select(Marca).where(Marca.nombre == "Charlie's Pizzas"))
    empresa = sembrado.scalar(select(Empresa))
    # La identidad es del grupo; la empresa la opera vía licencia.
    assert marca.grupo_id == empresa.grupo_id
    licencia = sembrado.scalar(
        select(LicenciaMarca).where(
            LicenciaMarca.empresa_id == empresa.id, LicenciaMarca.marca_id == marca.id
        )
    )
    assert licencia is not None


def test_dos_sucursales_activas_alquiladas(sembrado):
    sucursales = {
        s.nombre: s for s in sembrado.scalars(select(Sucursal)).all()
    }
    assert set(sucursales) == {"CH1", "CH2"}
    assert sucursales["CH1"].direccion == SEDE_CASTILLA
    assert sucursales["CH2"].direccion == "Jr. Lamas 299 - Tarapoto"
    marca = sembrado.scalar(select(Marca))
    empresa = sembrado.scalar(select(Empresa))
    for sucursal in sucursales.values():
        assert sucursal.estado == "activa"
        # Local alquilado: no paga predial ni arbitrios (RN-IMP-004).
        assert sucursal.tenencia == "alquilada"
        assert sucursal.marca_id == marca.id
        assert sucursal.empresa_id == empresa.id


def test_almacen_central_sin_sucursal(sembrado):
    almacen = sembrado.scalar(select(Almacen))
    assert almacen.nombre == "WH1"
    assert almacen.tipo == "central"
    assert almacen.direccion == SEDE_CASTILLA
    # El central no cuelga de ninguna sucursal: abastece a todas.
    assert almacen.sucursal_id is None
    assert almacen.almacen_abastecedor_id is None
    assert almacen.empresa_id == sembrado.scalar(select(Empresa.id))


def test_permiso_gestionar_parametros_empresa_sembrado_y_solo_admin(sembrado):
    """Aprobar parámetros (ADR-014) no cuelga de ningún rol operativo: solo
    de `admin` vía `*` — no hay rol `gerente` explícito todavía."""
    permiso = sembrado.scalar(
        select(Permiso).where(Permiso.codigo == "gerencia.gestionar_parametros_empresa")
    )
    assert permiso is not None

    roles_con_el_permiso = set(
        sembrado.scalars(
            select(Rol.nombre)
            .join(RolPermiso, RolPermiso.rol_id == Rol.id)
            .where(RolPermiso.permiso_id == permiso.id)
        )
    )
    assert roles_con_el_permiso == set()


def test_permiso_proponer_parametro_sembrado_por_modulo(sembrado):
    """Un permiso por módulo (ADR-014 Addendum): Compras no puede proponer
    parámetros de RRHH. Ninguno cuelga aún de un rol operativo."""
    codigos = set(
        sembrado.scalars(
            select(Permiso.codigo).where(Permiso.codigo.like("%.proponer_parametro"))
        )
    )
    assert codigos == {f"{modulo}.proponer_parametro" for modulo in MODULOS}

    admin = sembrado.scalar(select(Rol).where(Rol.nombre == "admin"))
    admin_permisos = set(
        sembrado.scalars(
            select(Permiso.codigo)
            .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
            .where(RolPermiso.rol_id == admin.id)
        )
    )
    assert admin_permisos == {"*"}  # admin autoriza todo por wildcard, no fila por fila


def test_seed_es_idempotente(sembrado):
    seed(sembrado)

    for modelo in (Grupo, Empresa, Marca, LicenciaMarca, Almacen):
        assert sembrado.scalar(select(func.count()).select_from(modelo)) == 1
    assert sembrado.scalar(select(func.count()).select_from(Sucursal)) == 2


def test_seed_actualiza_el_domicilio_fiscal_de_una_empresa_ya_sembrada(session):
    grupo = Grupo(nombre="Grupo Majambo")
    session.add(grupo)
    session.flush()
    session.add(
        Empresa(
            grupo_id=grupo.id,
            razon_social="Inversiones Turísticas y Alimentarias Majambo EIRL",
            ruc="20450311520",
            domicilio_fiscal="Tarapoto, San Martín",
            tipo="operativa",
            zona_tributaria="amazonia_ley27037",
        )
    )
    session.commit()

    seed(session)

    empresa = session.scalar(select(Empresa))
    assert empresa.domicilio_fiscal == SEDE_CASTILLA


def test_usuarios_semilla_con_su_rol_y_todas_las_sucursales(sembrado):
    """Sin `usuario_sucursal` el JWT sale sin `empresa_id` (ADR-004): cada
    usuario semilla necesita rol Y sucursales, no solo existir."""
    sucursales = sembrado.scalar(select(func.count()).select_from(Sucursal))
    for username, nombre_rol in USUARIOS_SEMILLA:
        usuario = sembrado.scalar(
            select(Usuario).where(Usuario.username == username)
        )
        assert usuario is not None and usuario.activo
        rol = sembrado.scalar(select(Rol).where(Rol.nombre == nombre_rol))
        assert sembrado.get(UsuarioRol, (usuario.id, rol.id)) is not None
        asignadas = sembrado.scalar(
            select(func.count())
            .select_from(UsuarioSucursal)
            .where(UsuarioSucursal.usuario_id == usuario.id)
        )
        assert asignadas == sucursales
