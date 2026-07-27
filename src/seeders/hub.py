"""Alta de la cuenta de servicio de un hub de sucursal (ADR-009).

Una por sucursal, `usuario.tipo=agente_ia`, con el rol `hub_sucursal`
(solo `sync.leer` + `sync.empujar`) y alcance a esa única sucursal — de
ahí sale el tenant que la API de sync aplica a todo lo que el hub pide.

A diferencia de `seed.py`, esto SÍ corre en producción: es el alta real de
un local. Idempotente: repetirlo sobre un hub ya dado de alta no duplica
nada (y no cambia el PIN salvo que se pida con `--rotar-pin`).

Uso:
    python -m src.seeders.hub --sucursal <uuid> --username hub_tarapoto
    # el PIN se pide por consola; --pin solo para automatizar el alta
"""

import argparse
import getpass
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.modules.users.domain import rules
from src.modules.users.infrastructure.models import (
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin

ROL_HUB = "hub_sucursal"


def alta_hub(
    session: Session,
    sucursal_id: uuid.UUID,
    username: str,
    pin: str,
    rotar_pin: bool = False,
) -> Usuario:
    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None:
        raise ValueError(f"sucursal {sucursal_id} no existe")
    rol = session.scalar(select(Rol).where(Rol.nombre == ROL_HUB))
    if rol is None:
        raise ValueError(
            f"falta el rol '{ROL_HUB}'; correr el seeder de permisos primero"
        )

    usuario = session.scalar(select(Usuario).where(Usuario.username == username))
    if usuario is None:
        usuario = Usuario(
            username=username,
            pin_hash=hash_pin(pin),
            tipo="agente_ia",
            nombre_display=f"Hub {sucursal.nombre}",
            activo=True,
        )
        session.add(usuario)
        session.flush()
    elif rotar_pin:
        usuario.pin_hash = hash_pin(pin)

    if session.get(UsuarioRol, (usuario.id, rol.id)) is None:
        session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    # Exactamente una sucursal: la API de sync rechaza una cuenta con más
    # de una, para que un hub no pueda leer datos de otro local.
    otras = session.scalars(
        select(UsuarioSucursal).where(UsuarioSucursal.usuario_id == usuario.id)
    )
    for asignacion in otras:
        if asignacion.sucursal_id != sucursal_id:
            session.delete(asignacion)
    if session.get(UsuarioSucursal, (usuario.id, sucursal_id)) is None:
        session.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal_id))
    return usuario


def main() -> int:
    parser = argparse.ArgumentParser(description="Alta de cuenta de servicio de hub")
    parser.add_argument("--sucursal", required=True, help="UUID de la sucursal")
    parser.add_argument("--username", required=True, help="ej. hub_tarapoto")
    parser.add_argument("--pin", help="si se omite, se pide por consola")
    parser.add_argument(
        "--rotar-pin",
        action="store_true",
        help="reemplaza el PIN de una cuenta de hub ya existente",
    )
    args = parser.parse_args()

    pin = args.pin or getpass.getpass("PIN del hub: ")
    if not rules.pin_valido(pin):
        print(f"El PIN debe ser exactamente {rules.PIN_LENGTH} dígitos", file=sys.stderr)
        return 1

    with SessionLocal() as session:
        try:
            usuario = alta_hub(
                session,
                uuid.UUID(args.sucursal),
                args.username,
                pin,
                rotar_pin=args.rotar_pin,
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
        session.commit()
        print(f"Hub dado de alta: {usuario.username} ({usuario.id})")
        print("Configurar en el .env del hub: CLOUD_SYNC_USERNAME y CLOUD_SYNC_PIN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
