"""API de reportes y tableros.

Vive en `core` por lo mismo que `dashboard_router`: compone contratos
públicos de varios módulos y no le pertenece a ninguno. Nunca importa el
dominio de un módulo — solo `application/queries_publicas`, vía el catálogo.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.core.reportes import catalogo, rangos
from src.core.tenant import Tenant
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Rol, Usuario, UsuarioRol
from src.modules.users.infrastructure.repositories import UsuarioRepo
from src.shared.models import Tablero

router = APIRouter(prefix="/reportes", tags=["reportes"])
router_tableros = APIRouter(prefix="/tableros", tags=["reportes"])

LEER = "dashboard.leer"

ANCHOS = (1, 2, 3, 4)
ALTOS = ("chico", "mediano", "grande")


class ColumnaOut(BaseModel):
    clave: str
    titulo: str
    tipo: str


class ReporteOut(BaseModel):
    codigo: str
    nombre: str
    descripcion: str
    visual: str
    visuales: list[str]
    etiqueta: str
    valor: str
    filtra_sucursal: bool
    columnas: list[ColumnaOut]


class CatalogoOut(BaseModel):
    reportes: list[ReporteOut]
    # El frontend no repite la lista de presets ni la traduce por su cuenta.
    rangos: dict[str, str]


class FiltrosIn(BaseModel):
    preset: str = "mes_actual"
    desde: date | None = None
    hasta: date | None = None
    # Vacío = todas las sucursales del alcance del usuario, no "todas".
    sucursal_ids: list[uuid.UUID] = Field(default_factory=list)
    limite: int = Field(default=catalogo.LIMITE_DEFECTO, ge=1)


class DatosOut(BaseModel):
    codigo: str
    desde: date
    hasta: date
    columnas: list[ColumnaOut]
    # `Decimal` sale como string exacto (no float): un total de dinero no
    # puede perder centavos al serializarse.
    filas: list[dict[str, Any]]


def _a_salida(r: catalogo.Reporte) -> ReporteOut:
    return ReporteOut(
        codigo=r.codigo,
        nombre=r.nombre,
        descripcion=r.descripcion,
        visual=r.visual,
        visuales=list(r.visuales),
        etiqueta=r.etiqueta,
        valor=r.valor,
        filtra_sucursal=r.filtra_sucursal,
        columnas=[
            ColumnaOut(clave=c.clave, titulo=c.titulo, tipo=c.tipo) for c in r.columnas
        ],
    )


def _permisos(session: Session, usuario: Usuario) -> set[str]:
    return UsuarioRepo(session).permiso_codigos(usuario.id)


def _sucursales_efectivas(
    tenant: Tenant, pedidas: list[uuid.UUID]
) -> list[uuid.UUID] | None:
    """Qué sucursales entran en el reporte.

    Sin selección explícita **no** se devuelve "todas": se devuelven las del
    usuario. Un cajero de Tarapoto que no toca el filtro tiene que ver
    Tarapoto, no la empresa entera. `None` (sin filtro) queda solo para el
    superusuario sin sucursales asignadas, que es la cuenta de setup.
    """
    if pedidas:
        for s in pedidas:
            tenant.exigir_sucursal(s)  # 403 vía el handler de FueraDeAlcance
        return pedidas
    if tenant.sucursal_ids:
        return sorted(tenant.sucursal_ids)
    return None


@router.get("", response_model=CatalogoOut)
def listar_catalogo(
    usuario: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Solo los reportes que este usuario puede pedir: el catálogo mismo es
    una lista de capacidades, no se muestra lo que después daría 403."""
    return CatalogoOut(
        reportes=[_a_salida(r) for r in catalogo.visibles(list(_permisos(session, usuario)))],
        rangos=rangos.ETIQUETAS,
    )


@router.post("/{codigo}/datos", response_model=DatosOut)
def datos(
    codigo: str,
    filtros: FiltrosIn,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    reporte = catalogo.obtener(codigo)
    if reporte is None:
        raise HTTPException(404, "Reporte no encontrado")
    # Doble puerta: `dashboard.leer` abre el tablero, el permiso del módulo
    # dueño abre *este* reporte.
    if reporte not in catalogo.visibles(list(_permisos(session, usuario))):
        raise HTTPException(403, "Permiso denegado")

    try:
        desde, hasta = rangos.resolver(filtros.preset, filtros.desde, filtros.hasta)
    except rangos.RangoInvalido as e:
        raise HTTPException(422, str(e)) from e

    filas = catalogo.ejecutar(
        reporte,
        session,
        tenant.filtro_empresa(),
        desde=desde,
        hasta=hasta,
        sucursal_ids=_sucursales_efectivas(tenant, filtros.sucursal_ids),
        limite=filtros.limite,
    )
    return DatosOut(
        codigo=reporte.codigo,
        desde=desde,
        hasta=hasta,
        columnas=_a_salida(reporte).columnas,
        filas=[_serializar(f) for f in filas],
    )


def _serializar(fila: dict) -> dict:
    """`Decimal` → string exacto, `date`/`UUID` → ISO. Sin esto pydantic
    convertiría los montos a float y un total de S/ 0.10 dejaría de sumar."""
    salida = {}
    for clave, valor in fila.items():
        if isinstance(valor, Decimal):
            salida[clave] = str(valor)
        elif isinstance(valor, date | uuid.UUID):
            salida[clave] = str(valor)
        else:
            salida[clave] = valor
    return salida


# --- Tableros ---------------------------------------------------------------
class TarjetaIn(BaseModel):
    codigo: str
    titulo: str | None = Field(default=None, max_length=100)
    visual: Literal["tabla", "barras", "lineas"] = "tabla"
    ancho: Annotated[int, Field(ge=1, le=4)] = 2
    alto: Literal["chico", "mediano", "grande"] = "mediano"


class TableroIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    predeterminado: bool = False
    tarjetas: list[TarjetaIn] = Field(default_factory=list, max_length=24)
    filtros: FiltrosIn = Field(default_factory=FiltrosIn)
    # NULL = privado. Con rol, lo ve en solo lectura quien tenga ese rol.
    rol_id: uuid.UUID | None = None


class RolOut(BaseModel):
    id: uuid.UUID
    nombre: str


class TableroOut(BaseModel):
    id: uuid.UUID
    nombre: str
    predeterminado: bool
    tarjetas: list[Any]
    filtros: dict[str, Any]
    rol_id: uuid.UUID | None = None
    # Calculados para el cliente: un tablero compartido por otro se muestra
    # pero no se edita, y la UI necesita saberlo sin recalcular quién es
    # dueño de qué.
    propio: bool = True
    compartido_por: str | None = None


def _validar_tarjetas(
    tarjetas: list[TarjetaIn], permitidos: list[catalogo.Reporte]
) -> None:
    """Un tablero no puede guardar un reporte inexistente ni uno que su
    dueño no puede ver — si no, bastaría guardarlo para saltarse el RBAC en
    la próxima carga."""
    por_codigo = {r.codigo: r for r in permitidos}
    for t in tarjetas:
        reporte = por_codigo.get(t.codigo)
        if reporte is None:
            raise HTTPException(422, f"Reporte '{t.codigo}' no existe o no es visible")
        if t.visual not in reporte.visuales:
            raise HTTPException(
                422, f"'{t.visual}' no es una vista válida de '{t.codigo}'"
            )


def _a_json(tarjetas: list[TarjetaIn]) -> list[dict]:
    return [t.model_dump() for t in tarjetas]


def _mio(session: Session, tablero_id: uuid.UUID, usuario: Usuario) -> Tablero:
    tablero = session.get(Tablero, tablero_id)
    # Mismo 404 si no existe o si es de otro: la respuesta no confirma la
    # existencia del tablero ajeno.
    if tablero is None or tablero.usuario_id != usuario.id:
        raise HTTPException(404, "Tablero no encontrado")
    return tablero


def _desmarcar_otros(session: Session, usuario_id: uuid.UUID) -> None:
    for otro in session.scalars(
        select(Tablero).where(
            Tablero.usuario_id == usuario_id, Tablero.predeterminado.is_(True)
        )
    ):
        otro.predeterminado = False


def _roles_de(session: Session, usuario_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(UsuarioRol.rol_id).where(UsuarioRol.usuario_id == usuario_id)
        )
    )


def _validar_rol(
    session: Session, rol_id: uuid.UUID | None, usuario: Usuario, superusuario: bool
) -> None:
    """Solo se comparte hacia un rol propio.

    Sin esta regla cualquiera podría publicar tableros en la bandeja de
    Gerencia o de Contabilidad sin pertenecer a ninguna de las dos: no es
    una fuga de datos (cada reporte revalida su permiso) pero sí una vía
    para llenarle la pantalla a un área ajena.
    """
    if rol_id is None or superusuario:
        return
    if rol_id not in _roles_de(session, usuario.id):
        raise HTTPException(422, "Solo se puede compartir con un rol propio")


def _a_salida_tablero(tablero: Tablero, usuario: Usuario, dueno: str | None) -> TableroOut:
    propio = tablero.usuario_id == usuario.id
    return TableroOut(
        id=tablero.id,
        nombre=tablero.nombre,
        predeterminado=tablero.predeterminado,
        tarjetas=tablero.tarjetas,
        filtros=tablero.filtros,
        rol_id=tablero.rol_id,
        propio=propio,
        compartido_por=None if propio else dueno,
    )


@router_tableros.get("/roles", response_model=list[RolOut])
def roles_para_compartir(
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Los roles con los que este usuario puede compartir. Un superusuario
    los ve todos; el resto, los suyos. Declarada antes de `/{tablero_id}`:
    si quedara después, "roles" se intentaría parsear como UUID."""
    stmt = select(Rol)
    if not tenant.superusuario:
        stmt = stmt.where(Rol.id.in_(_roles_de(session, usuario.id)))
    return list(session.scalars(stmt.order_by(Rol.nombre)))


@router_tableros.get("", response_model=list[TableroOut])
def listar_tableros(
    usuario: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Los míos, más los que alguien compartió con un rol que tengo."""
    mios = Tablero.usuario_id == usuario.id
    roles = _roles_de(session, usuario.id)
    condicion = or_(mios, Tablero.rol_id.in_(roles)) if roles else mios

    tableros = list(
        session.scalars(
            select(Tablero)
            .where(condicion)
            .order_by(Tablero.predeterminado.desc(), Tablero.nombre)
        )
    )
    # Nombre del dueño solo para los ajenos, en una consulta y no en bucle.
    ajenos = {t.usuario_id for t in tableros if t.usuario_id != usuario.id}
    duenos = (
        dict(
            session.execute(
                select(Usuario.id, Usuario.username).where(Usuario.id.in_(ajenos))
            ).all()
        )
        if ajenos
        else {}
    )
    return [_a_salida_tablero(t, usuario, duenos.get(t.usuario_id)) for t in tableros]


@router_tableros.post("", response_model=TableroOut, status_code=201)
def crear_tablero(
    body: TableroIn,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    _validar_tarjetas(body.tarjetas, catalogo.visibles(list(_permisos(session, usuario))))
    _validar_rol(session, body.rol_id, usuario, tenant.superusuario)
    if body.predeterminado:
        _desmarcar_otros(session, usuario.id)
    tablero = Tablero(
        empresa_id=tenant.empresa(),
        usuario_id=usuario.id,
        nombre=body.nombre,
        predeterminado=body.predeterminado,
        tarjetas=_a_json(body.tarjetas),
        filtros=body.filtros.model_dump(mode="json"),
        rol_id=body.rol_id,
    )
    session.add(tablero)
    session.commit()
    return _a_salida_tablero(tablero, usuario, None)


@router_tableros.patch("/{tablero_id}", response_model=TableroOut)
def actualizar_tablero(
    tablero_id: uuid.UUID,
    body: TableroIn,
    usuario: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    # `_mio`: un tablero compartido lo ve todo su rol, pero lo edita su dueño.
    tablero = _mio(session, tablero_id, usuario)
    _validar_tarjetas(body.tarjetas, catalogo.visibles(list(_permisos(session, usuario))))
    _validar_rol(session, body.rol_id, usuario, tenant.superusuario)
    if body.predeterminado and not tablero.predeterminado:
        _desmarcar_otros(session, usuario.id)
    tablero.nombre = body.nombre
    tablero.predeterminado = body.predeterminado
    tablero.tarjetas = _a_json(body.tarjetas)
    tablero.filtros = body.filtros.model_dump(mode="json")
    tablero.rol_id = body.rol_id
    session.commit()
    return _a_salida_tablero(tablero, usuario, None)


@router_tableros.delete("/{tablero_id}", status_code=204)
def borrar_tablero(
    tablero_id: uuid.UUID,
    usuario: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    session.delete(_mio(session, tablero_id, usuario))
    session.commit()
