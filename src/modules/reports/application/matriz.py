"""La matriz de distribución: el hub.

Una sola pantalla que responde las tres preguntas que motivaron el módulo:
qué reporta el ERP, a qué áreas y usuarios llega cada cosa, y **dónde está
roto** — qué hecho ocurre sin llegarle a nadie (hueco) y qué regla apunta a
un conjunto vacío de personas (fuga).

Los huecos y las fugas son la mitad del valor. Una matriz que solo muestra lo
configurado se ve completa siempre; lo que un administrador necesita ver es
lo que *falta*.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.reports.application import destinatarios as resolucion
from src.modules.reports.domain import catalogo
from src.modules.reports.infrastructure.models import Area, ReglaDestinatario
from src.modules.reports.infrastructure.repositories import ReglaRepo
from src.modules.users.infrastructure.models import Rol, Sucursal, Usuario


def _etiquetas(session: Session, empresa_id: uuid.UUID | None) -> dict[str, dict]:
    """Nombres de áreas, roles, usuarios y sucursales en cuatro consultas.

    La alternativa —resolver el nombre de cada destinatario dentro del
    bucle— son N consultas para una pantalla que se pinta entera de una vez.
    """
    areas = select(Area)
    sucursales = select(Sucursal)
    if empresa_id is not None:
        areas = areas.where(Area.empresa_id == empresa_id)
        sucursales = sucursales.where(Sucursal.empresa_id == empresa_id)
    return {
        "area": {a.id: a.nombre for a in session.scalars(areas)},
        "rol": dict(session.execute(select(Rol.id, Rol.nombre)).all()),
        "usuario": dict(session.execute(select(Usuario.id, Usuario.username)).all()),
        "sucursal": {s.id: s.nombre for s in session.scalars(sucursales)},
    }


def _describir(destinatario: ReglaDestinatario, etiquetas: dict[str, dict]) -> dict:
    referencia = (
        destinatario.area_id
        or destinatario.rol_id
        or destinatario.usuario_id
        or destinatario.dinamico
    )
    etiqueta = (
        destinatario.dinamico.replace("_", " ")
        if destinatario.tipo == "dinamico"
        else etiquetas[destinatario.tipo].get(referencia, "(borrado)")
    )
    return {
        "tipo": destinatario.tipo,
        "id": str(referencia) if not isinstance(referencia, str) else None,
        "etiqueta": etiqueta,
    }


def construir(
    session: Session,
    *,
    empresa_id: uuid.UUID | None,
    permisos: set[str],
) -> list[dict]:
    """Una fila por emisión que el usuario puede ver, con sus reglas.

    Se recorta por permiso igual que el catálogo de `core/reportes`: la
    matriz misma es una lista de capacidades y mostrar una emisión que
    después daría 403 solo confunde.
    """
    repo = ReglaRepo(session)
    reglas = repo.list(empresa_id) if empresa_id is not None else repo.list()
    por_codigo: dict[str, list] = {}
    for regla in reglas:
        por_codigo.setdefault(regla.codigo_emision, []).append(regla)

    todos = repo.destinatarios_de([r.id for r in reglas])
    por_regla: dict[uuid.UUID, list[ReglaDestinatario]] = {}
    for destinatario in todos:
        por_regla.setdefault(destinatario.regla_id, []).append(destinatario)

    etiquetas = _etiquetas(session, empresa_id)
    salida = []
    for emision in catalogo.visibles(permisos):
        filas = []
        for regla in por_codigo.get(emision.codigo, []):
            suyos = por_regla.get(regla.id, [])
            estaticos = [d for d in suyos if d.tipo != "dinamico"]
            dinamicos = [d.dinamico for d in suyos if d.tipo == "dinamico"]
            # Cuántas personas alcanza hoy, sin contar los dinámicos: quién
            # está de turno depende del momento y estimarlo acá sería
            # inventar un número que cambia solo.
            alcance = len(
                resolucion.resolver(
                    session,
                    estaticos,
                    empresa_id=regla.empresa_id,
                    sucursal_id=regla.sucursal_id,
                    almacen_id=None,
                )
            )
            filas.append(
                {
                    "id": str(regla.id),
                    "sucursal_id": str(regla.sucursal_id) if regla.sucursal_id else None,
                    "sucursal": (
                        etiquetas["sucursal"].get(regla.sucursal_id, "(borrada)")
                        if regla.sucursal_id
                        else "Todas"
                    ),
                    "activa": regla.activa,
                    "nivel": regla.nivel,
                    "canal": regla.canal,
                    "destinatarios": [_describir(d, etiquetas) for d in suyos],
                    "alcance": alcance,
                    # Apunta a alguien, pero hoy ese alguien no es nadie: el
                    # área quedó vacía, o el rol no lo tiene ninguno de esa
                    # sucursal. El hecho va a ocurrir y no va a llegar.
                    "fuga": regla.activa and alcance == 0 and not dinamicos,
                }
            )
        activas = [f for f in filas if f["activa"]]
        salida.append(
            {
                "codigo": emision.codigo,
                "nombre": emision.nombre,
                "descripcion": emision.descripcion,
                "permiso": emision.permiso,
                "nivel": emision.nivel,
                "ambito": emision.ambito,
                "areas_sugeridas": list(emision.areas_sugeridas),
                "reglas": filas,
                # Nadie configuró la distribución de este hecho: ocurre y no
                # se entera nadie (RN-REP-005).
                "hueco": not activas,
            }
        )
    return salida
