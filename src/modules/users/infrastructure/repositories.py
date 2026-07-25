"""Repositorios SQLAlchemy del módulo users.

La sesión actúa como Unit of Work: la capa de aplicación decide cuándo hacer
commit/rollback. Los repos solo encapsulan las queries.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.users.infrastructure.models import (
    AuditLog,
    Permiso,
    RefreshToken,
    Rol,
    RolPermiso,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)


class UsuarioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, usuario_id: uuid.UUID) -> Usuario | None:
        return self.s.get(Usuario, usuario_id)

    def get_by_username(self, username: str) -> Usuario | None:
        return self.s.scalar(
            select(Usuario).where(
                Usuario.username == username, Usuario.deleted_at.is_(None)
            )
        )

    def list(self) -> list[Usuario]:
        return list(
            self.s.scalars(
                select(Usuario).where(Usuario.deleted_at.is_(None)).order_by(
                    Usuario.username
                )
            )
        )

    def add(self, usuario: Usuario) -> Usuario:
        self.s.add(usuario)
        self.s.flush()
        return usuario

    def sucursal_ids(self, usuario_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            self.s.scalars(
                select(UsuarioSucursal.sucursal_id).where(
                    UsuarioSucursal.usuario_id == usuario_id
                )
            )
        )

    def rol_nombres(self, usuario_id: uuid.UUID) -> list[str]:
        return list(
            self.s.scalars(
                select(Rol.nombre)
                .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
                .where(UsuarioRol.usuario_id == usuario_id)
            )
        )

    def permiso_codigos(self, usuario_id: uuid.UUID) -> set[str]:
        return set(
            self.s.scalars(
                select(Permiso.codigo)
                .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
                .join(UsuarioRol, UsuarioRol.rol_id == RolPermiso.rol_id)
                .where(UsuarioRol.usuario_id == usuario_id)
            )
        )


class RolRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, rol_id: uuid.UUID) -> Rol | None:
        return self.s.get(Rol, rol_id)

    def get_by_nombre(self, nombre: str) -> Rol | None:
        return self.s.scalar(select(Rol).where(Rol.nombre == nombre))

    def list(self) -> list[Rol]:
        return list(self.s.scalars(select(Rol).where(Rol.deleted_at.is_(None))))

    def add(self, rol: Rol) -> Rol:
        self.s.add(rol)
        self.s.flush()
        return rol


class PermisoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, permiso_id: uuid.UUID) -> Permiso | None:
        return self.s.get(Permiso, permiso_id)

    def get_by_codigo(self, codigo: str) -> Permiso | None:
        return self.s.scalar(select(Permiso).where(Permiso.codigo == codigo))

    def list(self) -> list[Permiso]:
        return list(self.s.scalars(select(Permiso).where(Permiso.deleted_at.is_(None))))

    def add(self, permiso: Permiso) -> Permiso:
        self.s.add(permiso)
        self.s.flush()
        return permiso


class RefreshTokenRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    def add(self, token: RefreshToken) -> RefreshToken:
        self.s.add(token)
        self.s.flush()
        return token

    def revocar_sesion(self, sesion_id: uuid.UUID) -> None:
        for tok in self.s.scalars(
            select(RefreshToken).where(RefreshToken.sesion_id == sesion_id)
        ):
            tok.revocado = True


class AuditLogRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def registrar(self, **campos) -> AuditLog:
        entry = AuditLog(**campos)
        self.s.add(entry)
        return entry
