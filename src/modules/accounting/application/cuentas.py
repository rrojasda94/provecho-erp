"""Casos de uso: plan de cuentas."""

import uuid

from sqlalchemy.orm import Session

from src.modules.accounting.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import CuentaContable
from src.modules.accounting.infrastructure.repositories import CuentaContableRepo


def crear_cuenta(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    codigo: str,
    nombre: str,
    tipo: str,
    cuenta_padre_id: uuid.UUID | None = None,
) -> CuentaContable:
    if tipo not in rules.TIPOS_CUENTA:
        raise ReglaNegocio(f"tipo de cuenta inválido: {tipo}")
    repo = CuentaContableRepo(session)
    if repo.get_by_codigo(empresa_id, codigo) is not None:
        raise Conflicto(f"ya existe la cuenta {codigo} en esta empresa")
    if cuenta_padre_id is not None:
        padre = repo.get(cuenta_padre_id)
        if padre is None or padre.empresa_id != empresa_id:
            raise NoEncontrado(f"cuenta padre {cuenta_padre_id} no encontrada")
    return repo.add(
        CuentaContable(
            empresa_id=empresa_id,
            codigo=codigo,
            nombre=nombre,
            tipo=tipo,
            cuenta_padre_id=cuenta_padre_id,
        )
    )


def listar_cuentas(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[CuentaContable]:
    return CuentaContableRepo(session).list(empresa_id)


def editar_cuenta(
    session: Session,
    cuenta_id: uuid.UUID,
    *,
    nombre: str | None = None,
    activa: bool | None = None,
) -> CuentaContable:
    cuenta = CuentaContableRepo(session).get(cuenta_id)
    if cuenta is None:
        raise NoEncontrado("cuenta contable no encontrada")
    if nombre is not None:
        cuenta.nombre = nombre
    if activa is not None:
        cuenta.activa = activa
    return cuenta
