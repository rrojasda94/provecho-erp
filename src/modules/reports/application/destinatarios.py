"""Quién recibe un reporte, y por qué.

Acá viven las dos funciones que estaban en
`users/application/notificaciones.py` (`destinatarios_de_sucursal`,
`destinatarios_de_almacen`). Su docstring ya declaraba que ese era «el punto
de configuración futuro»; este módulo es ese futuro. La diferencia es que
antes eran *la* regla y ahora son **dos resolutores entre cuatro tipos**: lo
que se elige por configuración es si se usan o no.

Se leen `Rol`, `UsuarioRol`, `UsuarioSucursal`, `Sucursal` y `Almacen` de
`users.infrastructure.models` — organización transversal, excepción `"*"` de
`tests/test_arquitectura.py` — y `encargado_de_turno` del contrato público
de `accounting`.

Toda función devuelve `[(usuario_id, motivo)]`. El **motivo** no es adorno:
es lo que después le dice al administrador qué tocar para cambiar quién
recibe qué.
"""

import logging
import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.accounting.application.queries_publicas import encargado_de_turno
from src.modules.reports.domain import catalogo, rules
from src.modules.reports.infrastructure.models import AreaMiembro, ReglaDestinatario
from src.modules.reports.infrastructure.repositories import AreaRepo
from src.modules.users.infrastructure.models import (
    Almacen,
    Rol,
    Sucursal,
    UsuarioRol,
    UsuarioSucursal,
)

log = logging.getLogger("provecho.app")

# Roles que cubren el local cuando no hay caja abierta que diga quién está de
# turno. En orden de cercanía a la operación. (Venía de `users`.)
ROLES_RESPALDO = ("supervisor", "admin")

# Quién responde por lo que pasa dentro de un almacén. `almacenero` primero
# porque es quien puede actuar; los otros dos porque tienen que enterarse.
ROLES_ALMACEN = ("almacenero", "supervisor", "admin")


def _usuarios_de_rol(
    session: Session,
    *,
    rol_id: uuid.UUID | None = None,
    nombres_rol: Sequence[str] | None = None,
    empresa_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """Los usuarios de un rol, acotados al local del hecho cuando lo hay.

    Sin acotar, un descuadre en Tarapoto le llegaría a los supervisores de
    todas las sucursales. Cuando el hecho no tiene sucursal (un pago sobre
    umbral es de la empresa), se abre a la empresa entera a propósito.
    """
    q = (
        select(UsuarioSucursal.usuario_id)
        .join(Sucursal, Sucursal.id == UsuarioSucursal.sucursal_id)
        .join(UsuarioRol, UsuarioRol.usuario_id == UsuarioSucursal.usuario_id)
        .distinct()
    )
    if rol_id is not None:
        q = q.where(UsuarioRol.rol_id == rol_id)
    if nombres_rol is not None:
        q = q.join(Rol, Rol.id == UsuarioRol.rol_id).where(Rol.nombre.in_(nombres_rol))
    if sucursal_id is not None:
        q = q.where(UsuarioSucursal.sucursal_id == sucursal_id)
    elif empresa_id is not None:
        q = q.where(Sucursal.empresa_id == empresa_id)
    return list(session.scalars(q))


def de_area(
    session: Session,
    area_id: uuid.UUID,
    *,
    empresa_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """Los miembros de un área: sus roles resueltos a personas, más las
    personas puestas a dedo.

    Un miembro con `sucursal_id` solo cuenta para hechos de esa sucursal —
    «el almacenero de Tarapoto es del área Almacén, pero solo para Tarapoto».
    """
    miembros = list(
        session.scalars(select(AreaMiembro).where(AreaMiembro.area_id == area_id))
    )
    salida: list[uuid.UUID] = []
    for miembro in miembros:
        if (
            miembro.sucursal_id is not None
            and sucursal_id is not None
            and miembro.sucursal_id != sucursal_id
        ):
            continue
        if miembro.usuario_id is not None:
            salida.append(miembro.usuario_id)
            continue
        salida += _usuarios_de_rol(
            session,
            rol_id=miembro.rol_id,
            empresa_id=empresa_id,
            # La membresía acotada manda sobre el ámbito del hecho.
            sucursal_id=miembro.sucursal_id or sucursal_id,
        )
    return salida


def de_sucursal(session: Session, sucursal_id: uuid.UUID) -> list[uuid.UUID]:
    """A quién se le avisa de algo que pasa en esta sucursal.

    1. El **encargado de turno**, derivado de la caja abierta: es quien está
       a cargo del local ahora mismo.
    2. Si no hay caja abierta (local cerrado, o abrieron sin registrarla),
       los `supervisor`/`admin` asignados a esa sucursal — un aviso sin
       destinatario es un aviso perdido, y prefiere avisarle a alguien de más
       que a nadie.

    (Migrada tal cual desde `users.application.notificaciones`.)
    """
    encargado = encargado_de_turno(session, sucursal_id)
    if encargado is not None:
        return [encargado]

    respaldo = _usuarios_de_rol(
        session,
        nombres_rol=ROLES_RESPALDO,
        empresa_id=None,
        sucursal_id=sucursal_id,
    )
    if not respaldo:
        log.warning(
            "Reporte sin destinatario: la sucursal no tiene caja abierta ni "
            "supervisores asignados",
            extra={"sucursal_id": str(sucursal_id)},
        )
    return respaldo


def de_almacen(
    session: Session,
    almacen_id: uuid.UUID,
    roles: tuple[str, ...] = ROLES_ALMACEN,
) -> list[uuid.UUID]:
    """A quién se le avisa de algo que pasa en un **almacén**.

    No alcanza con `de_sucursal`: el almacén central y el de producción no
    cuelgan de ninguna sucursal (`almacen.sucursal_id` NULL), y ahí no hay
    encargado de turno que valga.

    - Almacén **de sucursal**: los roles de almacén asignados a esa sucursal,
      más el encargado de turno — es quien está parado ahí ahora.
    - Almacén **de empresa** (central, producción): los roles de almacén de
      cualquier sucursal de esa empresa. Es más gente de la necesaria, y es a
      propósito: un aviso de stock del central sin destinatario es un aviso
      perdido.

    (Migrada tal cual desde `users.application.notificaciones`.)
    """
    almacen = session.get(Almacen, almacen_id)
    if almacen is None:
        return []

    salida = _usuarios_de_rol(
        session,
        nombres_rol=roles,
        empresa_id=almacen.empresa_id,
        sucursal_id=almacen.sucursal_id,
    )
    if almacen.sucursal_id is not None:
        encargado = encargado_de_turno(session, almacen.sucursal_id)
        if encargado is not None and encargado not in salida:
            salida.append(encargado)
    if not salida:
        log.warning(
            "Reporte sin destinatario: el almacén no tiene roles de almacén "
            "asignados en su empresa",
            extra={"almacen_id": str(almacen_id)},
        )
    return salida


def resolver(
    session: Session,
    destinatarios: Sequence[ReglaDestinatario],
    *,
    empresa_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None,
    almacen_id: uuid.UUID | None,
    contexto: Mapping | None = None,
) -> list[tuple[uuid.UUID, str]]:
    """Los destinatarios de una regla, resueltos a personas y deduplicados.

    Gana el **primer** motivo que trajo a cada persona: quien está en el área
    Almacén y además es el encargado de turno recibe una vez, y el motivo que
    queda es el que el administrador escribió primero en la regla.

    `contexto` es la proyección del payload **ya recortada por la whitelist**
    de la emisión (`catalogo.proyectar`). Un resolutor dinámico no puede ver
    más de lo que la emisión declaró: así la garantía de RN-REP-003 se
    extiende sola a los destinatarios.
    """
    encontrados: dict[uuid.UUID, str] = {}

    def sumar(ids: Sequence[uuid.UUID], motivo: str) -> None:
        for usuario_id in ids:
            encontrados.setdefault(usuario_id, motivo)

    for destinatario in destinatarios:
        if destinatario.tipo == "usuario" and destinatario.usuario_id is not None:
            sumar([destinatario.usuario_id], rules.motivo("usuario", ""))
        elif destinatario.tipo == "rol" and destinatario.rol_id is not None:
            sumar(
                _usuarios_de_rol(
                    session,
                    rol_id=destinatario.rol_id,
                    empresa_id=empresa_id,
                    sucursal_id=sucursal_id,
                ),
                rules.motivo("rol", str(destinatario.rol_id)),
            )
        elif destinatario.tipo == "area" and destinatario.area_id is not None:
            sumar(
                de_area(
                    session,
                    destinatario.area_id,
                    empresa_id=empresa_id,
                    sucursal_id=sucursal_id,
                ),
                rules.motivo("area", str(destinatario.area_id)),
            )
        elif destinatario.tipo == "dinamico":
            sumar(
                _dinamico(
                    session,
                    destinatario.dinamico,
                    empresa_id=empresa_id,
                    sucursal_id=sucursal_id,
                    almacen_id=almacen_id,
                    contexto=contexto,
                ),
                rules.motivo("dinamico", destinatario.dinamico or ""),
            )

    return list(encontrados.items())


def _dinamico(
    session: Session,
    nombre: str | None,
    *,
    empresa_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None,
    almacen_id: uuid.UUID | None,
    contexto: Mapping | None = None,
) -> list[uuid.UUID]:
    if nombre == "encargado_de_turno" and sucursal_id is not None:
        return de_sucursal(session, sucursal_id)
    if nombre == "responsables_de_almacen" and almacen_id is not None:
        return de_almacen(session, almacen_id)
    if nombre == "responsables_del_nivel":
        return del_nivel(
            session,
            (contexto or {}).get("nivel_actual"),
            empresa_id=empresa_id,
            # El escalamiento se emite con ámbito `empresa` (puede nacer de un
            # hecho sin local), así que la sucursal viene en su propio payload.
            sucursal_id=sucursal_id or _uuid(contexto, "sucursal_id"),
        )
    # Un dinámico que no aplica al ámbito del hecho (pedir el encargado de
    # turno de un pago de empresa) resuelve a nadie, no a todos.
    return []


def _uuid(contexto: Mapping | None, clave: str) -> uuid.UUID | None:
    """El payload viaja serializado (los ids son strings). Un valor ausente o
    inválido resuelve a nadie: un reporte no se pierde por un campo mal."""
    valor = (contexto or {}).get(clave)
    if isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor)) if valor else None
    except ValueError:
        return None


def del_nivel(
    session: Session,
    nivel: str | None,
    *,
    empresa_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """Quién responde en un nivel de la cadena de escalamiento (ADR-036).

    El ERP no tiene jerarquía organizacional —no hay `supervisor_id` ni nivel
    de rol—, así que el escalón se resuelve con lo que sí existe: el encargado
    de turno para el piso y las áreas para los dos de arriba
    (`catalogo.DESTINO_POR_NIVEL`).

    Es público porque el endpoint que eleva lo llama para responder **a quién
    le va a llegar**: el reporte de la elevación se emite post-commit
    (ADR-016), así que sus entregas todavía no existen cuando hay que
    contestar. Una lista vacía es la respuesta correcta cuando el nivel no
    tiene a nadie, y verla es el punto (RN-REP-005).
    """
    tipo, valor = catalogo.DESTINO_POR_NIVEL.get(nivel or "", (None, None))
    if tipo == "dinamico" and sucursal_id is not None:
        return de_sucursal(session, sucursal_id)
    if tipo == "area" and empresa_id is not None:
        area = AreaRepo(session).por_codigo(empresa_id, valor)
        if area is not None:
            return de_area(
                session, area.id, empresa_id=empresa_id, sucursal_id=sucursal_id
            )
    return []
