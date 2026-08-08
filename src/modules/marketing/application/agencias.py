"""Casos de uso de la evaluación agencia vs. interna (RN-MKT-006).

Tres pasos y dos manos: Marketing declara los criterios y carga las
propuestas (`crear_evaluacion` → `agregar_opcion` → `cerrar_evaluacion`),
Gerencia decide (`decidir`, con permiso propio). Que sean dos permisos
distintos es la regla, no una formalidad: quien arma la comparación no la
firma, igual que quien redacta el brief no lo aprueba (RN-MKT-003).

La agencia es un **servicio**: se formaliza por contrato y la paga
Contabilidad; no pasa por `purchases`, que compra el material (RN-MKT-004).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import agencia as reglas
from src.modules.marketing.infrastructure.models import EvaluacionAgencia, OpcionAgencia
from src.modules.marketing.infrastructure.repositories import (
    CampanaRepo,
    EvaluacionAgenciaRepo,
)

# Estados de campaña en los que evaluar tiene sentido: hace falta el brief
# aprobado para saber contra qué objetivo y qué presupuesto se compara.
ESTADOS_EVALUABLES = ("aprobada", "en_curso")


def crear_evaluacion(
    session: Session,
    *,
    campana_id: uuid.UUID,
    objetivo: str,
    presupuesto_referencia: Decimal,
    criterios: list[dict],
    creado_por: uuid.UUID,
) -> EvaluacionAgencia:
    campana = CampanaRepo(session).get(campana_id)
    if campana is None or campana.deleted_at is not None:
        raise NoEncontrado("campaña no encontrada")
    if campana.estado not in ESTADOS_EVALUABLES:
        raise Conflicto(
            f"la campaña está {campana.estado}; sin brief aprobado no hay "
            "objetivo ni presupuesto contra los cuales evaluar (RN-MKT-003)"
        )
    problemas = reglas.criterios_validos(criterios)
    if problemas:
        raise ReglaNegocio("criterios inválidos: " + "; ".join(problemas))

    return EvaluacionAgenciaRepo(session).add(
        EvaluacionAgencia(
            campana_id=campana_id,
            objetivo=objetivo,
            presupuesto_referencia=Decimal(str(presupuesto_referencia)),
            criterios=criterios,
            estado="borrador",
            creado_por=creado_por,
        )
    )


def agregar_opcion(
    session: Session,
    evaluacion_id: uuid.UUID,
    *,
    tipo: str,
    nombre: str,
    costo: Decimal,
    plazo_dias: int,
    puntajes: dict,
    proveedor_id: uuid.UUID | None = None,
    observacion: str | None = None,
) -> OpcionAgencia:
    evaluacion = _evaluacion(session, evaluacion_id)
    if evaluacion.estado != "borrador":
        raise Conflicto(
            f"la evaluación está {evaluacion.estado}; ya no admite propuestas"
        )
    problemas = reglas.puntajes_validos(evaluacion.criterios, puntajes)
    if problemas:
        raise ReglaNegocio("puntajes inválidos: " + "; ".join(problemas))

    opcion = OpcionAgencia(
        evaluacion_id=evaluacion_id,
        tipo=tipo,
        nombre=nombre,
        proveedor_id=proveedor_id,
        costo=Decimal(str(costo)),
        plazo_dias=plazo_dias,
        puntajes=puntajes,
        puntaje_total=reglas.puntaje_ponderado(evaluacion.criterios, puntajes),
        observacion=observacion,
    )
    session.add(opcion)
    session.flush()
    return opcion


def cerrar_evaluacion(session: Session, evaluacion_id: uuid.UUID) -> EvaluacionAgencia:
    """Cierra la carga de propuestas. Exige la opción **interna**: comparar
    tres agencias entre sí no contesta la pregunta de RN-MKT-006, que es si
    hace falta una agencia."""
    evaluacion = _evaluacion(session, evaluacion_id)
    if evaluacion.estado != "borrador":
        raise Conflicto(f"la evaluación está {evaluacion.estado}; ya se cerró")
    if not reglas.comparable([o.tipo for o in evaluacion.opciones]):
        raise ReglaNegocio(
            "hacen falta al menos dos propuestas y una de ellas tiene que ser "
            "la opción interna (RN-MKT-006)"
        )
    evaluacion.estado = "evaluada"
    session.flush()
    return evaluacion


def decidir(
    session: Session,
    evaluacion_id: uuid.UUID,
    *,
    opcion_id: uuid.UUID,
    decidida_por: uuid.UUID,
    motivo: str | None = None,
) -> EvaluacionAgencia:
    """Gerencia valida. Puede apartarse de la recomendación o del
    presupuesto, pero no en silencio: ahí el motivo es obligatorio."""
    evaluacion = _evaluacion(session, evaluacion_id)
    if evaluacion.estado != "evaluada":
        raise Conflicto(
            f"la evaluación está {evaluacion.estado}; se decide una vez cerrada"
        )
    elegida = next((o for o in evaluacion.opciones if o.id == opcion_id), None)
    if elegida is None:
        raise NoEncontrado("la propuesta no pertenece a esta evaluación")

    sugerida = recomendada(evaluacion)
    if reglas.exige_motivo(
        _propuesta(elegida), sugerida, evaluacion.presupuesto_referencia
    ) and not (motivo or "").strip():
        raise ReglaNegocio(
            "elegir una propuesta que no es la recomendada o que excede el "
            "presupuesto exige dejar el motivo por escrito (RN-GER-003)"
        )

    evaluacion.opcion_elegida_id = elegida.id
    evaluacion.decidida_por = decidida_por
    evaluacion.fecha_decision = datetime.now(UTC)
    evaluacion.motivo = motivo
    evaluacion.estado = "decidida"
    session.flush()
    event_bus.publish(
        "marketing.agencia_decidida",
        {
            "evaluacion_id": str(evaluacion.id),
            "campana_id": str(evaluacion.campana_id),
            "opcion_id": str(elegida.id),
            "tipo": elegida.tipo,
            "costo": str(elegida.costo),
            "fuera_de_presupuesto": elegida.costo > evaluacion.presupuesto_referencia,
        },
        session=session,
    )
    return evaluacion


def recomendada(evaluacion: EvaluacionAgencia) -> reglas.Propuesta | None:
    return reglas.recomendada(
        [_propuesta(o) for o in evaluacion.opciones],
        evaluacion.presupuesto_referencia,
    )


def _propuesta(opcion: OpcionAgencia) -> reglas.Propuesta:
    return reglas.Propuesta(
        id=str(opcion.id),
        tipo=opcion.tipo,
        costo=Decimal(str(opcion.costo)),
        puntaje_total=Decimal(str(opcion.puntaje_total)),
    )


def _evaluacion(session: Session, evaluacion_id: uuid.UUID) -> EvaluacionAgencia:
    evaluacion = EvaluacionAgenciaRepo(session).get(evaluacion_id)
    if evaluacion is None:
        raise NoEncontrado("evaluación de agencia no encontrada")
    return evaluacion
