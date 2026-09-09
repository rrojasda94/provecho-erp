"""Alta y gestión de repartidores propios (ADR-098).

Un repartidor es un trabajador con cuenta que además reparte con un
vehículo propio de la empresa. `crear` resuelve la cuenta por
`rrhh.queries_publicas` — `delivery` no importa `Trabajador` ni `Persona`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.delivery.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.delivery.domain import rules
from src.modules.delivery.infrastructure.models import Repartidor
from src.modules.delivery.infrastructure.repositories import RepartidorRepo
from src.modules.rrhh.application.queries_publicas import (
    cuenta_de_trabajador,
    trabajadores_con_cuenta,
)


def con_nombre(session: Session, repartidor: Repartidor) -> dict:
    """El repartidor con el nombre de su cuenta ya resuelto: el tablero de
    despacho y el diálogo de "nueva ruta" eligen repartidor por nombre, no
    por id — `RepartidorOut` no lo traía porque el alta (`candidatos`) ya
    lo resolvía por su cuenta, pero listar/editar no."""
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    return {
        "id": repartidor.id,
        "empresa_id": repartidor.empresa_id,
        "sucursal_id": repartidor.sucursal_id,
        "trabajador_id": repartidor.trabajador_id,
        "usuario_id": repartidor.usuario_id,
        "nombre": cuenta["nombre"] if cuenta else None,
        "vehiculo_tipo": repartidor.vehiculo_tipo,
        "placa": repartidor.placa,
        "telefono": repartidor.telefono,
        "activo": repartidor.activo,
    }


def candidatos(session: Session, empresa_id: uuid.UUID) -> list[dict]:
    """Trabajadores con cuenta que todavía no son repartidor — lo que
    ofrece la pantalla de alta antes de elegir uno."""
    ya_repartidores = set(
        session.scalars(select(Repartidor.trabajador_id).where(Repartidor.deleted_at.is_(None)))
    )
    return [
        t
        for t in trabajadores_con_cuenta(session, empresa_id)
        if t["trabajador_id"] not in ya_repartidores
    ]


def crear(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    trabajador_id: uuid.UUID,
    sucursal_id: uuid.UUID,
    vehiculo_tipo: str,
    placa: str | None = None,
    telefono: str | None = None,
) -> Repartidor:
    if vehiculo_tipo not in rules.VEHICULOS:
        raise ReglaNegocio(f"vehículo desconocido: {vehiculo_tipo}")

    repo = RepartidorRepo(session)
    if repo.get_por_trabajador(trabajador_id) is not None:
        raise Conflicto("este trabajador ya es repartidor")

    cuenta = cuenta_de_trabajador(session, trabajador_id)
    if cuenta is None:
        raise Conflicto("el trabajador no existe, está cesado o no tiene cuenta propia")
    if cuenta["empresa_id"] != empresa_id:
        raise Conflicto("el trabajador no pertenece a esta empresa")
    if repo.get_por_usuario(cuenta["usuario_id"]) is not None:
        raise Conflicto("esta cuenta ya es de otro repartidor")

    repartidor = Repartidor(
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        trabajador_id=trabajador_id,
        usuario_id=cuenta["usuario_id"],
        vehiculo_tipo=vehiculo_tipo,
        placa=placa,
        telefono=telefono or cuenta.get("telefono"),
    )
    return repo.add(repartidor)


def editar(
    session: Session,
    repartidor_id: uuid.UUID,
    *,
    sucursal_id: uuid.UUID | None = None,
    vehiculo_tipo: str | None = None,
    placa: str | None = None,
    telefono: str | None = None,
    activo: bool | None = None,
) -> Repartidor:
    repartidor = RepartidorRepo(session).get(repartidor_id)
    if repartidor is None or repartidor.deleted_at is not None:
        raise NoEncontrado("repartidor no encontrado")

    if vehiculo_tipo is not None:
        if vehiculo_tipo not in rules.VEHICULOS:
            raise ReglaNegocio(f"vehículo desconocido: {vehiculo_tipo}")
        repartidor.vehiculo_tipo = vehiculo_tipo
    if sucursal_id is not None:
        repartidor.sucursal_id = sucursal_id
    if placa is not None:
        repartidor.placa = placa
    if telefono is not None:
        repartidor.telefono = telefono
    if activo is not None:
        repartidor.activo = activo
    session.flush()
    return repartidor
