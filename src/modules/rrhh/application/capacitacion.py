"""Casos de uso de `pacto_permanencia`: crear y calcular reembolso
proporcional al tiempo de permanencia no cumplido (RN-RRHH-006)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import PactoPermanencia
from src.modules.rrhh.infrastructure.repositories import PactoPermanenciaRepo, TrabajadorRepo


def crear_pacto_permanencia(
    session: Session,
    *,
    trabajador_id: uuid.UUID,
    capacitacion_descripcion: str,
    capacitacion_tipo: str,
    costo_financiado: Decimal,
    plazo_permanencia_meses: int,
    fecha_inicio: date,
    fecha_fin_compromiso: date,
) -> PactoPermanencia:
    if plazo_permanencia_meses <= 0:
        raise ReglaNegocio("plazo_permanencia_meses debe ser > 0")
    if costo_financiado <= 0:
        raise ReglaNegocio("costo_financiado debe ser > 0")
    if TrabajadorRepo(session).get(trabajador_id) is None:
        raise NoEncontrado(f"trabajador {trabajador_id} no encontrado")

    return PactoPermanenciaRepo(session).add(
        PactoPermanencia(
            trabajador_id=trabajador_id,
            capacitacion_descripcion=capacitacion_descripcion,
            capacitacion_tipo=capacitacion_tipo,
            costo_financiado=costo_financiado,
            plazo_permanencia_meses=plazo_permanencia_meses,
            fecha_inicio=fecha_inicio,
            fecha_fin_compromiso=fecha_fin_compromiso,
        )
    )


def calcular_reembolso(
    session: Session, pacto_id: uuid.UUID, *, fecha_calculo: date
) -> Decimal:
    pacto = PactoPermanenciaRepo(session).get(pacto_id)
    if pacto is None:
        raise NoEncontrado("pacto de permanencia no encontrado")
    meses_cumplidos = max(rules.meses_servicio(pacto.fecha_inicio, fecha_calculo), 0)
    return rules.calcular_reembolso_pacto(
        pacto.costo_financiado, pacto.plazo_permanencia_meses, meses_cumplidos
    )
