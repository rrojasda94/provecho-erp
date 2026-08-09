"""Casos de uso de reglas de distribución: el gobierno de «quién recibe qué».

Toda alta, cambio y baja deja rastro en `audit_log` con la foto anterior y la
nueva (RN-REP-007, ADR-031). Eso *es* la respuesta a «si hay modificaciones
en los flujos de trabajo»: `GET /api/v1/auditoria?entidad=regla_distribucion`
cuenta quién cambió qué y cuándo, sin que este módulo tenga que mantener su
propio historial en paralelo.

Los destinatarios se reemplazan en bloque al editar, nunca de a uno. Una
regla es una lista y editarla parcialmente (agregar acá, quitar allá) obliga
al cliente a mandar diffs y a la API a resolverlos — más superficie para
terminar con una regla a medio aplicar.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.modules.reports.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.reports.domain import catalogo, rules
from src.modules.reports.infrastructure.models import (
    Area,
    ReglaDestinatario,
    ReglaDistribucion,
)
from src.modules.reports.infrastructure.repositories import ReglaRepo
from src.modules.users.infrastructure.models import Rol, Sucursal, Usuario
from src.shared import auditoria


@dataclass(frozen=True)
class DestinatarioIn:
    tipo: str
    area_id: uuid.UUID | None = None
    rol_id: uuid.UUID | None = None
    usuario_id: uuid.UUID | None = None
    dinamico: str | None = None


def _foto(regla: ReglaDistribucion, destinatarios: list[ReglaDestinatario]) -> dict:
    return {
        "codigo_emision": regla.codigo_emision,
        "sucursal_id": str(regla.sucursal_id) if regla.sucursal_id else None,
        "activa": regla.activa,
        "nivel": regla.nivel,
        "canal": regla.canal,
        "destinatarios": sorted(
            rules.motivo(
                d.tipo,
                str(d.area_id or d.rol_id or d.usuario_id or d.dinamico or ""),
            )
            for d in destinatarios
        ),
    }


def _validar_destinatario(
    session: Session, empresa_id: uuid.UUID, entrada: DestinatarioIn
) -> None:
    if entrada.tipo not in rules.TIPOS_DESTINATARIO:
        raise ReglaNegocio(f"tipo de destinatario inválido: '{entrada.tipo}'")
    if entrada.tipo == "area":
        area = session.get(Area, entrada.area_id) if entrada.area_id else None
        if area is None:
            raise NoEncontrado("área no encontrada")
        if area.empresa_id != empresa_id:
            raise ReglaNegocio("el área no pertenece a la empresa de la regla")
    elif entrada.tipo == "rol":
        if not entrada.rol_id or session.get(Rol, entrada.rol_id) is None:
            raise NoEncontrado("rol no encontrado")
    elif entrada.tipo == "usuario":
        if not entrada.usuario_id or session.get(Usuario, entrada.usuario_id) is None:
            raise NoEncontrado("usuario no encontrado")
    elif entrada.dinamico not in catalogo.DINAMICOS:
        raise ReglaNegocio(
            f"resolutor dinámico desconocido: '{entrada.dinamico}'. "
            f"Los que existen: {', '.join(catalogo.DINAMICOS)}"
        )


def _reemplazar_destinatarios(
    session: Session,
    regla: ReglaDistribucion,
    entradas: list[DestinatarioIn],
) -> list[ReglaDestinatario]:
    repo = ReglaRepo(session)
    for viejo in repo.destinatarios(regla.id):
        session.delete(viejo)
    session.flush()
    nuevos = []
    for entrada in entradas:
        _validar_destinatario(session, regla.empresa_id, entrada)
        nuevos.append(
            repo.add_destinatario(
                ReglaDestinatario(
                    regla_id=regla.id,
                    tipo=entrada.tipo,
                    area_id=entrada.area_id if entrada.tipo == "area" else None,
                    rol_id=entrada.rol_id if entrada.tipo == "rol" else None,
                    usuario_id=entrada.usuario_id if entrada.tipo == "usuario" else None,
                    dinamico=entrada.dinamico if entrada.tipo == "dinamico" else None,
                )
            )
        )
    return nuevos


def _validar_cabecera(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    codigo_emision: str,
    sucursal_id: uuid.UUID | None,
    nivel: str,
    canal: str,
) -> None:
    # RN-REP-001: el catálogo es cerrado. Una regla no puede referirse a una
    # emisión que no existe — si pudiera, quedaría muda para siempre sin que
    # nadie se entere.
    if catalogo.obtener(codigo_emision) is None:
        raise ReglaNegocio(f"'{codigo_emision}' no está en el catálogo de emisiones")
    if nivel not in catalogo.NIVELES:
        raise ReglaNegocio(f"nivel inválido: '{nivel}'")
    if canal not in rules.CANALES:
        raise ReglaNegocio(f"canal inválido: '{canal}'")
    if sucursal_id is not None:
        sucursal = session.get(Sucursal, sucursal_id)
        if sucursal is None or sucursal.empresa_id != empresa_id:
            raise ReglaNegocio("la sucursal no pertenece a la empresa de la regla")


def crear_regla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    codigo_emision: str,
    sucursal_id: uuid.UUID | None = None,
    nivel: str = "aviso",
    canal: str = "bandeja",
    activa: bool = True,
    destinatarios: list[DestinatarioIn] | None = None,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> ReglaDistribucion:
    _validar_cabecera(
        session,
        empresa_id=empresa_id,
        codigo_emision=codigo_emision,
        sucursal_id=sucursal_id,
        nivel=nivel,
        canal=canal,
    )
    repo = ReglaRepo(session)
    ya = [
        r
        for r in repo.activas_de(empresa_id, codigo_emision)
        if r.sucursal_id == sucursal_id
    ]
    if ya:
        raise Conflicto(
            "ya hay una regla para esta emisión en ese ámbito (RN-REP-008); "
            "editarla en vez de crear una segunda"
        )

    regla = repo.add(
        ReglaDistribucion(
            empresa_id=empresa_id,
            codigo_emision=codigo_emision,
            sucursal_id=sucursal_id,
            nivel=nivel,
            canal=canal,
            activa=activa,
        )
    )
    creados = _reemplazar_destinatarios(session, regla, destinatarios or [])
    auditoria.registrar(
        session,
        entidad="regla_distribucion",
        accion="crear",
        entidad_id=regla.id,
        usuario_id=actor_id,
        datos_despues=_foto(regla, creados),
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ip=ip,
    )
    return regla


def editar_regla(
    session: Session,
    regla_id: uuid.UUID,
    *,
    nivel: str | None = None,
    canal: str | None = None,
    activa: bool | None = None,
    destinatarios: list[DestinatarioIn] | None = None,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> ReglaDistribucion:
    """Cambia la regla de acá en adelante. **No es retroactivo** (RN-REP-004):
    los `reporte_emitido` que ya salieron conservan su `regla_id` y sus
    entregas con el motivo de entonces."""
    repo = ReglaRepo(session)
    regla = repo.get(regla_id)
    if regla is None:
        raise NoEncontrado("regla no encontrada")
    antes = _foto(regla, repo.destinatarios(regla_id))

    if nivel is not None:
        if nivel not in catalogo.NIVELES:
            raise ReglaNegocio(f"nivel inválido: '{nivel}'")
        regla.nivel = nivel
    if canal is not None:
        if canal not in rules.CANALES:
            raise ReglaNegocio(f"canal inválido: '{canal}'")
        regla.canal = canal
    if activa is not None:
        regla.activa = activa
    actuales = (
        _reemplazar_destinatarios(session, regla, destinatarios)
        if destinatarios is not None
        else repo.destinatarios(regla_id)
    )

    auditoria.registrar(
        session,
        entidad="regla_distribucion",
        accion="editar",
        entidad_id=regla.id,
        usuario_id=actor_id,
        datos_antes=antes,
        datos_despues=_foto(regla, actuales),
        empresa_id=regla.empresa_id,
        sucursal_id=regla.sucursal_id,
        ip=ip,
    )
    return regla


def borrar_regla(
    session: Session,
    regla_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    ip: str | None = None,
) -> None:
    repo = ReglaRepo(session)
    regla = repo.get(regla_id)
    if regla is None:
        raise NoEncontrado("regla no encontrada")
    antes = _foto(regla, repo.destinatarios(regla_id))
    empresa_id, sucursal_id = regla.empresa_id, regla.sucursal_id

    for destinatario in repo.destinatarios(regla_id):
        session.delete(destinatario)
    # `reporte_emitido.regla_id` queda apuntando a una regla que ya no está:
    # es FK nullable y SQLAlchemy no la limpia sola, así que se desliga acá.
    # El histórico no se toca —el motivo de cada entrega sigue ahí— pero deja
    # de decir "producido por esta regla" cuando esa regla ya no existe.
    for reporte in _reportes_de(session, regla_id):
        reporte.regla_id = None
    session.delete(regla)

    auditoria.registrar(
        session,
        entidad="regla_distribucion",
        accion="borrar",
        entidad_id=regla_id,
        usuario_id=actor_id,
        datos_antes=antes,
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ip=ip,
    )


def _reportes_de(session: Session, regla_id: uuid.UUID):
    from sqlalchemy import select

    from src.modules.reports.infrastructure.models import ReporteEmitido

    return session.scalars(
        select(ReporteEmitido).where(ReporteEmitido.regla_id == regla_id)
    )
