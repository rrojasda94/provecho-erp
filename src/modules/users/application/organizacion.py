"""Casos de uso de la organización: grupo, empresa, marca, licencia de
marca, sucursal y almacén.

Hasta ahora esto solo existía en el seeder: dar de alta un local nuevo
obligaba a correr un script contra la base. Acá vive el CRUD real, con las
reglas que el seeder daba por buenas porque las escribía a mano:

- Una **sucursal opera una marca licenciada a su empresa** (`licencia_marca`
  es el permiso; sin licencia, la sucursal no puede existir).
- Un **almacén de sucursal** pertenece a una sucursal de su misma empresa,
  y su abastecedor también es de esa empresa.
- La **baja es lógica** (`deleted_at`) y se niega si quedan dependientes
  vivos: una empresa con sucursales, una marca con locales abiertos, un
  central del que otros almacenes se abastecen.

El alcance por tenant (quién puede tocar qué empresa) no vive acá sino en
el router, como en el resto del módulo: ADR-004 dice que sale del token.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.modules.users.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    LicenciaMarca,
    Marca,
    Sucursal,
)
from src.modules.users.infrastructure.repositories import (
    AlmacenRepo,
    AuditLogRepo,
    EmpresaRepo,
    GrupoRepo,
    LicenciaMarcaRepo,
    MarcaRepo,
    SucursalRepo,
)

# Tipo de almacén que sí cuelga de un local; el resto (central, producción,
# activos) no tiene sucursal. Ver data-model §1.
TIPO_ALMACEN_DE_SUCURSAL = "sucursal"


def _get(obj, nombre: str):
    if obj is None:
        raise NoEncontrado(f"{nombre} no encontrado")
    return obj


def _auditar(
    session: Session,
    actor_id: uuid.UUID | None,
    entidad: str,
    entidad_id: uuid.UUID,
    accion: str,
    antes: dict | None = None,
    despues: dict | None = None,
) -> None:
    AuditLogRepo(session).registrar(
        usuario_id=actor_id, entidad=entidad, entidad_id=entidad_id,
        accion=accion, datos_antes=antes, datos_despues=despues,
    )


def _aplicar(obj, campos: dict, permitidos: tuple[str, ...]) -> dict:
    """Asigna los campos presentes y devuelve el estado anterior de los que
    realmente cambiaron (lo que la auditoría guarda como `datos_antes`)."""
    antes = {}
    for campo in permitidos:
        nuevo = campos.get(campo)
        if nuevo is None or getattr(obj, campo) == nuevo:
            continue
        antes[campo] = str(getattr(obj, campo))
        setattr(obj, campo, nuevo)
    return antes


# --- Grupo ------------------------------------------------------------------
def crear_grupo(
    session: Session, *, nombre: str, actor_id: uuid.UUID | None = None
) -> Grupo:
    repo = GrupoRepo(session)
    if repo.get_by_nombre(nombre):
        raise Conflicto(f"grupo '{nombre}' ya existe")
    grupo = repo.add(Grupo(nombre=nombre))
    _auditar(session, actor_id, "grupo", grupo.id, "crear", despues={"nombre": nombre})
    return grupo


def listar_grupos(session: Session) -> list[Grupo]:
    return GrupoRepo(session).list()


def obtener_grupo(session: Session, grupo_id: uuid.UUID) -> Grupo:
    return _get(GrupoRepo(session).get(grupo_id), "grupo")


def editar_grupo(
    session: Session,
    grupo_id: uuid.UUID,
    *,
    nombre: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> Grupo:
    repo = GrupoRepo(session)
    grupo = _get(repo.get(grupo_id), "grupo")
    if nombre and nombre != grupo.nombre and repo.get_by_nombre(nombre):
        raise Conflicto(f"grupo '{nombre}' ya existe")
    antes = _aplicar(grupo, {"nombre": nombre}, ("nombre",))
    if antes:
        _auditar(
            session, actor_id, "grupo", grupo.id, "editar", antes,
            {"nombre": grupo.nombre},
        )
    return grupo


# --- Empresa ----------------------------------------------------------------
def crear_empresa(
    session: Session,
    *,
    grupo_id: uuid.UUID,
    razon_social: str,
    ruc: str,
    domicilio_fiscal: str,
    tipo: str,
    zona_tributaria: str = "general",
    contacto: str | None = None,
    config_fiscal: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> Empresa:
    _get(GrupoRepo(session).get(grupo_id), "grupo")
    repo = EmpresaRepo(session)
    if repo.get_by_ruc(ruc):
        raise Conflicto(f"RUC '{ruc}' ya existe")
    empresa = repo.add(
        Empresa(
            grupo_id=grupo_id,
            razon_social=razon_social,
            ruc=ruc,
            domicilio_fiscal=domicilio_fiscal,
            tipo=tipo,
            zona_tributaria=zona_tributaria,
            contacto=contacto,
            config_fiscal=config_fiscal,
        )
    )
    _auditar(
        session, actor_id, "empresa", empresa.id, "crear",
        despues={"razon_social": razon_social, "ruc": ruc},
    )
    return empresa


def listar_empresas(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[Empresa]:
    return EmpresaRepo(session).list(empresa_id)


def obtener_empresa(session: Session, empresa_id: uuid.UUID) -> Empresa:
    return _get(EmpresaRepo(session).get(empresa_id), "empresa")


EDITABLES_EMPRESA = (
    "razon_social",
    "ruc",
    "domicilio_fiscal",
    "contacto",
    "tipo",
    "zona_tributaria",
    "config_fiscal",
)


def editar_empresa(
    session: Session,
    empresa_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> Empresa:
    """`grupo_id` no es editable: mover una empresa de grupo arrastraría sus
    marcas licenciadas y su historia contable. Si algún día hace falta, es
    una operación con nombre propio, no un PATCH."""
    repo = EmpresaRepo(session)
    empresa = _get(repo.get(empresa_id), "empresa")
    ruc_nuevo = campos.get("ruc")
    if ruc_nuevo and ruc_nuevo != empresa.ruc:
        otra = repo.get_by_ruc(ruc_nuevo)
        if otra is not None and otra.id != empresa_id:
            raise Conflicto(f"RUC '{ruc_nuevo}' ya existe")
    antes = _aplicar(empresa, campos, EDITABLES_EMPRESA)
    if antes:
        _auditar(
            session, actor_id, "empresa", empresa.id, "editar", antes,
            {campo: str(getattr(empresa, campo)) for campo in antes},
        )
    return empresa


def dar_de_baja_empresa(
    session: Session, empresa_id: uuid.UUID, *, actor_id: uuid.UUID | None = None
) -> Empresa:
    """Baja lógica. Se niega con dependientes vivos: una empresa sin RUC
    activo pero con locales abiertos deja huérfanas ventas y compras."""
    empresa = _get(EmpresaRepo(session).get(empresa_id), "empresa")
    if SucursalRepo(session).list(empresa_id):
        raise Conflicto("la empresa tiene sucursales activas")
    if AlmacenRepo(session).list(empresa_id):
        raise Conflicto("la empresa tiene almacenes activos")
    empresa.deleted_at = datetime.now(UTC)
    _auditar(session, actor_id, "empresa", empresa.id, "baja")
    return empresa


# --- Marca ------------------------------------------------------------------
def crear_marca(
    session: Session,
    *,
    grupo_id: uuid.UUID,
    nombre: str,
    tipo: str,
    skins: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> Marca:
    _get(GrupoRepo(session).get(grupo_id), "grupo")
    repo = MarcaRepo(session)
    if repo.get_by_nombre(grupo_id, nombre):
        raise Conflicto(f"marca '{nombre}' ya existe en el grupo")
    marca = repo.add(Marca(grupo_id=grupo_id, nombre=nombre, tipo=tipo, skins=skins))
    _auditar(
        session, actor_id, "marca", marca.id, "crear",
        despues={"nombre": nombre, "tipo": tipo},
    )
    return marca


def obtener_marca(session: Session, marca_id: uuid.UUID) -> Marca:
    return _get(MarcaRepo(session).get(marca_id), "marca")


def editar_marca(
    session: Session,
    marca_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> Marca:
    repo = MarcaRepo(session)
    marca = _get(repo.get(marca_id), "marca")
    nombre_nuevo = campos.get("nombre")
    if nombre_nuevo and nombre_nuevo != marca.nombre:
        otra = repo.get_by_nombre(marca.grupo_id, nombre_nuevo)
        if otra is not None and otra.id != marca_id:
            raise Conflicto(f"marca '{nombre_nuevo}' ya existe en el grupo")
    antes = _aplicar(marca, campos, ("nombre", "tipo", "skins"))
    if antes:
        _auditar(session, actor_id, "marca", marca.id, "editar", antes)
    return marca


def dar_de_baja_marca(
    session: Session, marca_id: uuid.UUID, *, actor_id: uuid.UUID | None = None
) -> Marca:
    marca = _get(MarcaRepo(session).get(marca_id), "marca")
    if SucursalRepo(session).list(marca_id=marca_id):
        raise Conflicto("la marca tiene sucursales activas")
    if LicenciaMarcaRepo(session).de_marca(marca_id):
        raise Conflicto("la marca sigue licenciada a alguna empresa")
    marca.deleted_at = datetime.now(UTC)
    _auditar(session, actor_id, "marca", marca.id, "baja")
    return marca


# --- Licencia de marca (N:N empresa↔marca, modelo franquicia interna) -------
def otorgar_licencia(
    session: Session,
    empresa_id: uuid.UUID,
    marca_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> LicenciaMarca:
    """Idempotente. La marca y la empresa tienen que ser del mismo grupo: la
    identidad es del grupo (data-model §1) y licenciarla afuera sería otro
    contrato, no una fila."""
    empresa = _get(EmpresaRepo(session).get(empresa_id), "empresa")
    marca = _get(MarcaRepo(session).get(marca_id), "marca")
    if marca.grupo_id != empresa.grupo_id:
        raise ReglaNegocio("la marca pertenece a otro grupo empresarial")
    repo = LicenciaMarcaRepo(session)
    licencia = repo.get(empresa_id, marca_id)
    if licencia is not None:
        return licencia
    licencia = repo.add(LicenciaMarca(empresa_id=empresa_id, marca_id=marca_id))
    _auditar(
        session, actor_id, "licencia_marca", licencia.id, "otorgar",
        despues={"empresa_id": str(empresa_id), "marca_id": str(marca_id)},
    )
    return licencia


def listar_licencias(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[LicenciaMarca]:
    return LicenciaMarcaRepo(session).list(empresa_id)


def revocar_licencia(
    session: Session,
    empresa_id: uuid.UUID,
    marca_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
) -> None:
    repo = LicenciaMarcaRepo(session)
    licencia = _get(repo.get(empresa_id, marca_id), "licencia de marca")
    operando = [
        s
        for s in SucursalRepo(session).list(empresa_id, marca_id)
        if s.estado == "activa"
    ]
    if operando:
        raise Conflicto("la empresa opera sucursales activas con esa marca")
    _auditar(
        session, actor_id, "licencia_marca", licencia.id, "revocar",
        antes={"empresa_id": str(empresa_id), "marca_id": str(marca_id)},
    )
    repo.delete(licencia)


# --- Sucursal ---------------------------------------------------------------
def crear_sucursal(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    marca_id: uuid.UUID,
    nombre: str,
    direccion: str,
    tenencia: str,
    estado: str = "activa",
    horario_atencion: dict | None = None,
    actor_id: uuid.UUID | None = None,
) -> Sucursal:
    _exigir_licencia(session, empresa_id, marca_id)
    sucursal = SucursalRepo(session).add(
        Sucursal(
            empresa_id=empresa_id,
            marca_id=marca_id,
            nombre=nombre,
            direccion=direccion,
            tenencia=tenencia,
            estado=estado,
            horario_atencion=horario_atencion,
        )
    )
    _auditar(
        session, actor_id, "sucursal", sucursal.id, "crear",
        despues={"nombre": nombre, "empresa_id": str(empresa_id)},
    )
    return sucursal


def obtener_sucursal(session: Session, sucursal_id: uuid.UUID) -> Sucursal:
    return _get(SucursalRepo(session).get(sucursal_id), "sucursal")


def editar_sucursal(
    session: Session,
    sucursal_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> Sucursal:
    """Cerrar un local es `estado="inactiva"`, no una baja lógica: la
    sucursal sigue siendo el ancla de sus ventas, cajas y trabajadores, y
    reabrirla es cambiar un campo (mismo criterio que RN-GEN-006)."""
    sucursal = _get(SucursalRepo(session).get(sucursal_id), "sucursal")
    marca_nueva = campos.get("marca_id")
    if marca_nueva and marca_nueva != sucursal.marca_id:
        _exigir_licencia(session, sucursal.empresa_id, marca_nueva)
    antes = _aplicar(
        sucursal,
        campos,
        ("marca_id", "nombre", "direccion", "estado", "tenencia", "horario_atencion"),
    )
    if antes:
        _auditar(
            session, actor_id, "sucursal", sucursal.id, "editar", antes,
            {campo: str(getattr(sucursal, campo)) for campo in antes},
        )
    return sucursal


def _exigir_licencia(
    session: Session, empresa_id: uuid.UUID, marca_id: uuid.UUID
) -> None:
    _get(EmpresaRepo(session).get(empresa_id), "empresa")
    _get(MarcaRepo(session).get(marca_id), "marca")
    if LicenciaMarcaRepo(session).get(empresa_id, marca_id) is None:
        raise ReglaNegocio("la empresa no tiene licencia sobre esa marca")


# --- Almacén ----------------------------------------------------------------
def crear_almacen(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    tipo: str,
    sucursal_id: uuid.UUID | None = None,
    direccion: str | None = None,
    almacen_abastecedor_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Almacen:
    _get(EmpresaRepo(session).get(empresa_id), "empresa")
    _validar_almacen(session, empresa_id, tipo, sucursal_id, almacen_abastecedor_id)
    almacen = AlmacenRepo(session).add(
        Almacen(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            nombre=nombre,
            tipo=tipo,
            direccion=direccion,
            almacen_abastecedor_id=almacen_abastecedor_id,
        )
    )
    _auditar(
        session, actor_id, "almacen", almacen.id, "crear",
        despues={"nombre": nombre, "tipo": tipo, "empresa_id": str(empresa_id)},
    )
    return almacen


def obtener_almacen(session: Session, almacen_id: uuid.UUID) -> Almacen:
    return _get(AlmacenRepo(session).get(almacen_id), "almacen")


def editar_almacen(
    session: Session,
    almacen_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None = None,
    **campos,
) -> Almacen:
    almacen = _get(AlmacenRepo(session).get(almacen_id), "almacen")
    # `None` = "no tocar" (ver schemas), así que el valor a validar es el
    # nuevo si vino y el vigente si no. Con `campos.get(k, actual)` un PATCH
    # que no menciona `sucursal_id` validaría contra None y rechazaría
    # cualquier edición de un almacén de sucursal.
    tipo = campos.get("tipo") or almacen.tipo
    sucursal_id = campos.get("sucursal_id") or almacen.sucursal_id
    abastecedor_id = (
        campos.get("almacen_abastecedor_id") or almacen.almacen_abastecedor_id
    )
    if abastecedor_id == almacen_id:
        raise ReglaNegocio("un almacén no puede abastecerse a sí mismo")
    _validar_almacen(session, almacen.empresa_id, tipo, sucursal_id, abastecedor_id)
    antes = _aplicar(
        almacen,
        campos,
        ("nombre", "tipo", "direccion", "sucursal_id", "almacen_abastecedor_id"),
    )
    if antes:
        _auditar(
            session, actor_id, "almacen", almacen.id, "editar", antes,
            {campo: str(getattr(almacen, campo)) for campo in antes},
        )
    return almacen


def dar_de_baja_almacen(
    session: Session, almacen_id: uuid.UUID, *, actor_id: uuid.UUID | None = None
) -> Almacen:
    """ponytail: no mira el stock — vive en `inventory` y `users` no importa
    el dominio de otro módulo (CLAUDE.md). Lo que sí puede ver es quién se
    abastece de él. El día que dar de baja un almacén con stock sea un
    problema real, va por evento, no por import (ROADMAP → Deuda técnica)."""
    repo = AlmacenRepo(session)
    almacen = _get(repo.get(almacen_id), "almacen")
    if repo.abastecidos_por(almacen_id):
        raise Conflicto("otros almacenes se abastecen de este")
    almacen.deleted_at = datetime.now(UTC)
    _auditar(session, actor_id, "almacen", almacen.id, "baja")
    return almacen


def _validar_almacen(
    session: Session,
    empresa_id: uuid.UUID,
    tipo: str,
    sucursal_id: uuid.UUID | None,
    almacen_abastecedor_id: uuid.UUID | None,
) -> None:
    if tipo == TIPO_ALMACEN_DE_SUCURSAL and sucursal_id is None:
        raise ReglaNegocio("un almacén de tipo 'sucursal' exige sucursal_id")
    if sucursal_id is not None:
        sucursal = _get(SucursalRepo(session).get(sucursal_id), "sucursal")
        if sucursal.empresa_id != empresa_id:
            raise ReglaNegocio("la sucursal pertenece a otra empresa")
    if almacen_abastecedor_id is not None:
        abastecedor = _get(
            AlmacenRepo(session).get(almacen_abastecedor_id), "almacen abastecedor"
        )
        if abastecedor.empresa_id != empresa_id:
            raise ReglaNegocio("el almacén abastecedor pertenece a otra empresa")
