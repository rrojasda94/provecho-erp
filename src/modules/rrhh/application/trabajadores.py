"""Casos de uso de `trabajador`: crear, actualizar, cesar, listar.

El modelo existía desde el slice de ventas (ranking por trabajador) sin capa
de aplicación — este slice se la agrega completa.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.rrhh.infrastructure.repositories import TrabajadorRepo
from src.modules.users.infrastructure.models import Empresa, Persona


def crear_trabajador(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    persona_id: uuid.UUID,
    cargo: str,
    area: str,
    tipo_vinculo: str,
    fecha_ingreso: date,
    usuario_id: uuid.UUID | None = None,
    regimen_laboral: str | None = None,
    remuneracion_base: Decimal | None = None,
    sistema_pensiones: str | None = None,
    afp_nombre: str | None = None,
    tiene_poderes: bool = False,
    registra_asistencia: bool = True,
    jornada_horas_semana: Decimal | None = None,
) -> Trabajador:
    if tipo_vinculo not in rules.TIPOS_VINCULO:
        raise ReglaNegocio(f"tipo_vinculo inválido: {tipo_vinculo}")
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    if session.get(Persona, persona_id) is None:
        raise NoEncontrado(f"persona {persona_id} no encontrada")

    if tipo_vinculo == "locacion_servicios":
        registra_asistencia = False
    if not rules.valida_registra_asistencia(tipo_vinculo, registra_asistencia):
        raise ReglaNegocio(
            "locación de servicios no registra asistencia (RN-PER-002)"
        )
    if (
        tipo_vinculo == "practicante"
        and remuneracion_base is not None
        and jornada_horas_semana is not None
    ):
        if not rules.valida_subvencion_practicante(
            remuneracion_base, jornada_horas_semana, settings.rrhh_rmv_vigente
        ):
            raise ReglaNegocio(
                "subvención de practicante bajo 1 RMV con jornada máxima (RN-PER-001)"
            )

    return TrabajadorRepo(session).add(
        Trabajador(
            empresa_id=empresa_id,
            persona_id=persona_id,
            usuario_id=usuario_id,
            cargo=cargo,
            area=area,
            tipo_vinculo=tipo_vinculo,
            regimen_laboral=regimen_laboral,
            fecha_ingreso=fecha_ingreso,
            remuneracion_base=remuneracion_base,
            sistema_pensiones=sistema_pensiones,
            afp_nombre=afp_nombre,
            tiene_poderes=tiene_poderes,
            registra_asistencia=registra_asistencia,
        )
    )


def listar_trabajadores(session: Session, empresa_id: uuid.UUID | None = None) -> list[Trabajador]:
    return TrabajadorRepo(session).list(empresa_id)


def actualizar_trabajador(session: Session, trabajador_id: uuid.UUID, **campos) -> Trabajador:
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado("trabajador no encontrado")
    for campo, valor in campos.items():
        if valor is not None:
            setattr(trabajador, campo, valor)
    return trabajador


def cesar_trabajador(
    session: Session, trabajador_id: uuid.UUID, *, fecha_cese: date
) -> Trabajador:
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado("trabajador no encontrado")
    if not rules.puede_cesar_trabajador(trabajador.estado):
        raise Conflicto(f"trabajador está {trabajador.estado}; no admite cese")
    trabajador.estado = "cesado"
    trabajador.fecha_cese = fecha_cese
    event_bus.publish(
        "rrhh.trabajador_cesado",
        {
            "trabajador_id": str(trabajador.id),
            "empresa_id": str(trabajador.empresa_id),
            "usuario_id": str(trabajador.usuario_id) if trabajador.usuario_id else None,
            "fecha_cese": fecha_cese.isoformat(),
        },
    )
    return trabajador
