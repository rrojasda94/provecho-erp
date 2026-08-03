"""Repositorios SQLAlchemy del módulo users.

La sesión actúa como Unit of Work: la capa de aplicación decide cuándo hacer
commit/rollback. Los repos solo encapsulan las queries.
"""

# `UsuarioRepo` define un método `list`, que dentro del cuerpo de la clase
# pisa el builtin `list` — sin esto, anotaciones como `-> list[uuid.UUID]`
# en métodos definidos después (`sucursal_ids`, `rol_nombres`) revientan con
# "'function' object is not subscriptable" en Python <3.14 (evaluación eager
# de anotaciones). Con este import las anotaciones quedan como string y
# nunca se evalúan así.
from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.modules.users.infrastructure.models import (
    Almacen,
    AuditLog,
    Permiso,
    Persona,
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

    def restricciones(self, usuario_id: uuid.UUID, codigo: str) -> dict | None:
        """`restricciones` (JSONB) del permiso `codigo` para este usuario.

        `None` = sin restricción: comodín `*`, o alguno de los roles que le
        dan `codigo` lo otorga sin condición (basta uno libre para no
        acotar — mismo criterio OR que `permite`). Llamar solo tras
        confirmar el permiso con `permite`/`check_permission`; sin ninguna
        fila que lo otorgue también devuelve `None` (nada que restringir).
        """
        from src.modules.users.domain.rules import PERMISO_TODO

        filas = list(
            self.s.scalars(
                select(Permiso)
                .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
                .join(UsuarioRol, UsuarioRol.rol_id == RolPermiso.rol_id)
                .where(
                    UsuarioRol.usuario_id == usuario_id,
                    Permiso.codigo.in_((codigo, PERMISO_TODO)),
                )
            )
        )
        if any(p.codigo == PERMISO_TODO for p in filas):
            return None
        if not filas or any(p.restricciones is None for p in filas):
            return None
        # ponytail: primera fila con restricciones — fusionar caps distintos
        # de dos roles sobre el mismo permiso el día que los datos sembrados
        # realmente lo hagan (hoy un usuario tiene un solo rol que otorga
        # cada código).
        return filas[0].restricciones


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


class PersonaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, persona_id: uuid.UUID) -> Persona | None:
        return self.s.scalar(
            select(Persona).where(
                Persona.id == persona_id, Persona.deleted_at.is_(None)
            )
        )

    def get_by_documento(self, numero_documento: str) -> Persona | None:
        return self.s.scalar(
            select(Persona).where(
                Persona.numero_documento == numero_documento,
                Persona.deleted_at.is_(None),
            )
        )

    def list(self, q: str | None = None) -> list[Persona]:
        stmt = select(Persona).where(Persona.deleted_at.is_(None))
        if q:
            patron = f"%{q}%"
            stmt = stmt.where(
                (Persona.nombres.ilike(patron))
                | (Persona.apellidos.ilike(patron))
                | (Persona.numero_documento.ilike(patron))
            )
        return list(self.s.scalars(stmt.order_by(Persona.apellidos, Persona.nombres)))

    def add(self, persona: Persona) -> Persona:
        self.s.add(persona)
        self.s.flush()
        return persona

    def actualizar_con_lock(
        self, persona_id: uuid.UUID, expected_version: int, **campos
    ) -> Persona | None:
        """UPDATE condicional atómico. Devuelve None si no hay fila afectada
        (version desactualizada — la capa de aplicación distingue el 404 de
        la existencia previa del 409 de conflicto de version)."""
        campos = {k: v for k, v in campos.items() if v is not None}
        campos["version"] = Persona.version + 1
        resultado = self.s.execute(
            update(Persona)
            .where(Persona.id == persona_id, Persona.version == expected_version)
            .values(**campos)
        )
        if resultado.rowcount == 0:
            return None
        self.s.flush()
        return self.get(persona_id)


class AlmacenRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Almacen]:
        stmt = select(Almacen).where(Almacen.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Almacen.empresa_id == empresa_id)
        return list(self.s.scalars(stmt.order_by(Almacen.nombre)))


class AuditLogRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def registrar(self, **campos) -> AuditLog:
        entry = AuditLog(**campos)
        self.s.add(entry)
        return entry
