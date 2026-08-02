"""Lectura de parámetros operativos configurables por empresa (ADR-014).

Único punto que los módulos deben consultar. Solo devuelve valores en estado
`vigente`: una propuesta pendiente de aprobación de Gerencia es invisible
para el módulo — ese es todo el mecanismo de "no surte efecto hasta que
Gerencia lo apruebe".
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.shared.repositories import ParametroEmpresaRepo

# Módulos que pueden tener parámetros. Es el nombre del **módulo de código**
# (`accounting`, `sales`), no el del área de negocio (`contabilidad`,
# `comercial`) — mismo criterio que `docs/domain/process-nomenclature.md`:
# el código de área no reemplaza el nombre del módulo técnico.
MODULOS = (
    "accounting",
    "inventory",
    "marketing",
    "production",
    "purchases",
    "rrhh",
    "sales",
    "users",
)


def permiso_proponer(modulo: str) -> str:
    """Permiso que habilita a un área a proponer un cambio de parámetro de su
    propio módulo. Un módulo desconocido no puede mapear a un permiso real."""
    if modulo not in MODULOS:
        raise ValueError(f"módulo desconocido: {modulo}")
    return f"{modulo}.proponer_parametro"


def valor_vigente(
    session: Session,
    empresa_id: uuid.UUID,
    modulo: str,
    codigo: str,
    default: Any = None,
) -> Any:
    """Valor aprobado para `empresa_id`/`modulo`/`codigo`, o `default`
    (valor semilla del propio módulo) si Gerencia no aprobó ninguno."""
    parametro = ParametroEmpresaRepo(session).get_vigente(empresa_id, modulo, codigo)
    return parametro.valor if parametro is not None else default
