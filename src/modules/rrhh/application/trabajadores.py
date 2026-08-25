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
from src.modules.users.application.queries_publicas import obtener_usuario
from src.modules.users.infrastructure.models import Empresa, Persona, Sucursal


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
    sucursal_id: uuid.UUID | None = None,
) -> Trabajador:
    if tipo_vinculo not in rules.TIPOS_VINCULO:
        raise ReglaNegocio(f"tipo_vinculo inválido: {tipo_vinculo}")
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    if session.get(Persona, persona_id) is None:
        raise NoEncontrado(f"persona {persona_id} no encontrada")
    _exigir_sucursal_de_empresa(session, sucursal_id, empresa_id)
    _exigir_cuenta_asignable(session, usuario_id, trabajador_id=None)

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
            sucursal_id=sucursal_id,
        )
    )


def listar_trabajadores(session: Session, empresa_id: uuid.UUID | None = None) -> list[Trabajador]:
    return TrabajadorRepo(session).list(empresa_id)


def q_trabajadores(session: Session, empresa_id: uuid.UUID | None = None):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return TrabajadorRepo(session).q_list(empresa_id)


# Campos que sí se pueden dejar en blanco: un `None` explícito los borra en vez
# de significar "no tocar". Para el resto, `None` sigue siendo "no tocar" —
# mandar `cargo: null` no puede vaciar una columna obligatoria.
#
# `usuario_id` es borrable porque quitarle la cuenta a quien dejó de usarla es
# una operación real: el router manda `exclude_unset`, así que omitirlo sigue
# significando "no tocar" y solo un `null` explícito desvincula.
BORRABLES = frozenset({"sucursal_id", "usuario_id"})


def actualizar_trabajador(session: Session, trabajador_id: uuid.UUID, **campos) -> Trabajador:
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado("trabajador no encontrado")
    if "sucursal_id" in campos:
        _exigir_sucursal_de_empresa(session, campos["sucursal_id"], trabajador.empresa_id)
    if "usuario_id" in campos:
        _exigir_cuenta_asignable(session, campos["usuario_id"], trabajador_id=trabajador_id)
    for campo, valor in campos.items():
        if valor is not None or campo in BORRABLES:
            setattr(trabajador, campo, valor)
    return trabajador


def _exigir_cuenta_asignable(
    session: Session,
    usuario_id: uuid.UUID | None,
    *,
    trabajador_id: uuid.UUID | None,
) -> None:
    """La cuenta que se le asigna a un trabajador tiene que existir, ser de
    una persona y no estar ya en uso por otro trabajador.

    Importa porque de este vínculo cuelga el pad de asistencia: el PIN que
    firma la marcación es el de esta cuenta (RN-RRHH-020). Una cuenta de
    agente no tiene PIN que teclear —entra por token (ADR-032)— y una cuenta
    compartida por dos trabajadores dejaría al pad sin saber cuál de los dos
    fichó.

    Se lee por el contrato público de `users`, no por su repositorio.
    """
    if usuario_id is None:
        return
    usuario = obtener_usuario(session, usuario_id)
    if usuario is None:
        raise NoEncontrado(f"usuario {usuario_id} no encontrado")
    if usuario.tipo != "humano":
        raise ReglaNegocio(
            "una cuenta de agente no marca asistencia: no tiene PIN que teclear"
        )
    if not usuario.activo:
        raise ReglaNegocio("la cuenta está desactivada")
    en_uso = TrabajadorRepo(session).por_usuario(usuario_id)
    if en_uso is not None and en_uso.id != trabajador_id:
        raise Conflicto("esa cuenta ya es de otro trabajador")


def _exigir_sucursal_de_empresa(
    session: Session, sucursal_id: uuid.UUID | None, empresa_id: uuid.UUID
) -> None:
    """El centro de labores tiene que ser un local de la misma empresa
    (RN-RRHH-019). Sin esto, un trabajador de una empresa del grupo podía
    quedar asignado al local de otra y arrastrar su planilla ahí."""
    if sucursal_id is None:
        return
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        raise NoEncontrado(f"sucursal {sucursal_id} no encontrada")
    if sucursal.empresa_id != empresa_id:
        raise ReglaNegocio(
            "la sucursal no es de la empresa del trabajador (RN-RRHH-019)"
        )


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
        session=session,
    )
    return trabajador
