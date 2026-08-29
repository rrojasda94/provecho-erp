"""Caso de uso: sembrar el Plan Contable General Empresarial en una empresa.

Idempotente por código: vuelve a correrse sin duplicar nada y sin tocar lo
que la empresa ya tenía. Una cuenta que la empresa creó a mano con un código
del PCGE se respeta tal cual —no se le pisa el nombre—: quien la creó sabía
para qué la quería.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.accounting.domain import pcge
from src.modules.accounting.infrastructure.models import CuentaContable
from src.modules.accounting.infrastructure.repositories import CuentaContableRepo


def importar_pcge(session: Session, *, empresa_id: uuid.UUID) -> dict[str, int]:
    """Crea las cuentas del PCGE que le falten a la empresa.

    Devuelve `{creadas, existentes, total}`. El árbol se arma en memoria y se
    escribe de una sola vez: son ~400 cuentas y un flush por cuenta convertía
    el alta de una empresa en 400 viajes a la base.
    """
    repo = CuentaContableRepo(session)
    codigos = [codigo for codigo, _ in pcge.CUENTAS]
    conocidas = repo.get_by_codigos(empresa_id, codigos)
    creadas = 0

    for codigo, nombre in pcge.CUENTAS:
        if codigo in conocidas:
            continue
        codigo_padre = pcge.padre_de(codigo)
        padre = conocidas.get(codigo_padre) if codigo_padre else None
        # El id se asigna acá y no en el INSERT: la divisionaria necesita el
        # id de su rubro y el rubro todavía no pasó por la base.
        cuenta = CuentaContable(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            codigo=codigo,
            nombre=nombre,
            tipo=pcge.tipo_de(codigo),
            cuenta_padre_id=padre.id if padre is not None else None,
        )
        session.add(cuenta)
        conocidas[codigo] = cuenta
        creadas += 1

    session.flush()
    return {
        "creadas": creadas,
        "existentes": len(pcge.CUENTAS) - creadas,
        "total": len(pcge.CUENTAS),
    }
