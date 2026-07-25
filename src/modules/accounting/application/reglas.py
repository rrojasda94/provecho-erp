"""Casos de uso: mapeo evento→cuentas (`regla_asiento`) que alimenta la
generación automática de asientos (RN-CTB-003, ver `application/listeners.py`)."""

import uuid

from sqlalchemy.orm import Session

from src.modules.accounting.application.errors import Conflicto, NoEncontrado
from src.modules.accounting.infrastructure.models import ReglaAsiento
from src.modules.accounting.infrastructure.repositories import (
    CuentaContableRepo,
    ReglaAsientoRepo,
)


def crear_regla_asiento(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    cuenta_debe_id: uuid.UUID,
    cuenta_haber_id: uuid.UUID,
) -> ReglaAsiento:
    repo = ReglaAsientoRepo(session)
    if repo.get_vigente(empresa_id, evento) is not None:
        raise Conflicto(f"ya existe una regla vigente para el evento {evento}")
    cuentas = CuentaContableRepo(session)
    for cuenta_id in (cuenta_debe_id, cuenta_haber_id):
        cuenta = cuentas.get(cuenta_id)
        if cuenta is None or cuenta.empresa_id != empresa_id:
            raise NoEncontrado(f"cuenta {cuenta_id} no encontrada")
    return repo.add(
        ReglaAsiento(
            empresa_id=empresa_id,
            evento=evento,
            cuenta_debe_id=cuenta_debe_id,
            cuenta_haber_id=cuenta_haber_id,
        )
    )


def listar_reglas_asiento(session: Session, empresa_id: uuid.UUID) -> list[ReglaAsiento]:
    return ReglaAsientoRepo(session).list(empresa_id)
