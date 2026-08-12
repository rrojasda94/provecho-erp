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

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    LicenciaMarca,
    Marca,
    Permiso,
    Persona,
    RefreshToken,
    Rol,
    RolPermiso,
    Sucursal,
    TokenAgente,
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

    def q_list(self):
        """La consulta, sin ejecutar: el router la pagina (ADR-026)."""
        return (
            select(Usuario)
            .where(Usuario.deleted_at.is_(None))
            .order_by(Usuario.username)
        )

    def list(self) -> list[Usuario]:
        return list(self.s.scalars(self.q_list()))

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

    def roles_de(self, usuario_id: uuid.UUID) -> list[Rol]:
        """Los roles asignados, con id y descripción — `rol_nombres` solo
        devuelve el nombre y la pantalla de administración necesita poder
        quitar el rol, o sea su id."""
        return list(
            self.s.scalars(
                select(Rol)
                .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
                .where(UsuarioRol.usuario_id == usuario_id)
                .order_by(Rol.nombre)
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

    def permisos_de(self, rol_id: uuid.UUID) -> list[Permiso]:
        """Qué habilita este rol. Sin esto, la pantalla de roles muestra
        nombres sueltos y nadie sabe qué está asignando."""
        return list(
            self.s.scalars(
                select(Permiso)
                .join(RolPermiso, RolPermiso.permiso_id == Permiso.id)
                .where(RolPermiso.rol_id == rol_id, Permiso.deleted_at.is_(None))
                .order_by(Permiso.codigo)
            )
        )

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

    def revocar_usuario(self, usuario_id: uuid.UUID) -> None:
        """Todas las sesiones de una cuenta, no solo la del request. Lo usa el
        reseteo de PIN: si se resetea por sospecha, dejar viva la sesión que
        ya estaba abierta no cierra nada."""
        for tok in self.s.scalars(
            select(RefreshToken).where(
                RefreshToken.usuario_id == usuario_id,
                RefreshToken.revocado.is_(False),
            )
        ):
            tok.revocado = True


class TokenAgenteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, token_id: uuid.UUID) -> TokenAgente | None:
        return self.s.get(TokenAgente, token_id)

    def get_by_hash(self, token_hash: str) -> TokenAgente | None:
        return self.s.scalar(
            select(TokenAgente).where(TokenAgente.token_hash == token_hash)
        )

    def list(self, usuario_id: uuid.UUID) -> list[TokenAgente]:
        return list(
            self.s.scalars(
                select(TokenAgente)
                .where(TokenAgente.usuario_id == usuario_id)
                .order_by(TokenAgente.created_at.desc())
            )
        )

    def add(self, token: TokenAgente) -> TokenAgente:
        self.s.add(token)
        self.s.flush()
        return token


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

    def q_list(self, q: str | None = None):
        stmt = select(Persona).where(Persona.deleted_at.is_(None))
        if q:
            patron = f"%{q}%"
            stmt = stmt.where(
                (Persona.nombres.ilike(patron))
                | (Persona.apellidos.ilike(patron))
                | (Persona.numero_documento.ilike(patron))
            )
        return stmt.order_by(Persona.apellidos, Persona.nombres)

    def list(self, q: str | None = None) -> list[Persona]:
        return list(self.s.scalars(self.q_list(q)))

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


class GrupoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, grupo_id: uuid.UUID) -> Grupo | None:
        return self.s.get(Grupo, grupo_id)

    def get_by_nombre(self, nombre: str) -> Grupo | None:
        return self.s.scalar(select(Grupo).where(Grupo.nombre == nombre))

    def list(self) -> list[Grupo]:
        return list(self.s.scalars(select(Grupo).order_by(Grupo.nombre)))

    def add(self, grupo: Grupo) -> Grupo:
        self.s.add(grupo)
        self.s.flush()
        return grupo


class EmpresaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, empresa_id: uuid.UUID) -> Empresa | None:
        return self.s.scalar(
            select(Empresa).where(
                Empresa.id == empresa_id, Empresa.deleted_at.is_(None)
            )
        )

    def get_by_ruc(self, ruc: str) -> Empresa | None:
        return self.s.scalar(
            select(Empresa).where(Empresa.ruc == ruc, Empresa.deleted_at.is_(None))
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Empresa]:
        """Con `empresa_id` devuelve solo esa: quien no es superusuario ve
        únicamente la empresa de su tenant, no el listado del grupo."""
        stmt = select(Empresa).where(Empresa.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Empresa.id == empresa_id)
        return list(self.s.scalars(stmt.order_by(Empresa.razon_social)))

    def add(self, empresa: Empresa) -> Empresa:
        self.s.add(empresa)
        self.s.flush()
        return empresa


class LicenciaMarcaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, empresa_id: uuid.UUID, marca_id: uuid.UUID) -> LicenciaMarca | None:
        return self.s.scalar(
            select(LicenciaMarca).where(
                LicenciaMarca.empresa_id == empresa_id,
                LicenciaMarca.marca_id == marca_id,
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[LicenciaMarca]:
        stmt = select(LicenciaMarca)
        if empresa_id is not None:
            stmt = stmt.where(LicenciaMarca.empresa_id == empresa_id)
        return list(self.s.scalars(stmt))

    def de_marca(self, marca_id: uuid.UUID) -> list[LicenciaMarca]:
        return list(
            self.s.scalars(
                select(LicenciaMarca).where(LicenciaMarca.marca_id == marca_id)
            )
        )

    def add(self, licencia: LicenciaMarca) -> LicenciaMarca:
        self.s.add(licencia)
        self.s.flush()
        return licencia

    def delete(self, licencia: LicenciaMarca) -> None:
        self.s.delete(licencia)


class AlmacenRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, almacen_id: uuid.UUID) -> Almacen | None:
        return self.s.scalar(
            select(Almacen).where(
                Almacen.id == almacen_id, Almacen.deleted_at.is_(None)
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Almacen]:
        stmt = select(Almacen).where(Almacen.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Almacen.empresa_id == empresa_id)
        return list(self.s.scalars(stmt.order_by(Almacen.nombre)))

    def abastecidos_por(self, almacen_id: uuid.UUID) -> list[Almacen]:
        """Los que se abastecen de este, **como principal o como respaldo**.
        Dar de baja al central sin mirarlos dejaría a media empresa apuntando
        a un almacén que ya no existe — y un respaldo que no existe es peor
        que no tenerlo, porque nadie se entera hasta que hace falta."""
        return list(
            self.s.scalars(
                select(Almacen).where(
                    or_(
                        Almacen.almacen_abastecedor_id == almacen_id,
                        Almacen.almacen_abastecedor_respaldo_id == almacen_id,
                    ),
                    Almacen.deleted_at.is_(None),
                )
            )
        )

    def add(self, almacen: Almacen) -> Almacen:
        self.s.add(almacen)
        self.s.flush()
        return almacen


class MarcaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, marca_id: uuid.UUID) -> Marca | None:
        return self.s.scalar(
            select(Marca).where(Marca.id == marca_id, Marca.deleted_at.is_(None))
        )

    def get_by_nombre(self, grupo_id: uuid.UUID, nombre: str) -> Marca | None:
        return self.s.scalar(
            select(Marca).where(
                Marca.grupo_id == grupo_id,
                Marca.nombre == nombre,
                Marca.deleted_at.is_(None),
            )
        )

    def add(self, marca: Marca) -> Marca:
        self.s.add(marca)
        self.s.flush()
        return marca

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Marca]:
        """Marcas que la empresa opera, vía sus sucursales.

        La marca es del **grupo**, no de la empresa (una marca licenciada
        puede operarla más de una): el filtro sale de qué marcas tienen
        sucursal en esta empresa. Sin `empresa_id` (superusuario) van todas.
        """
        stmt = select(Marca).where(Marca.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(
                Marca.id.in_(
                    select(Sucursal.marca_id).where(Sucursal.empresa_id == empresa_id)
                )
            )
        return list(self.s.scalars(stmt.order_by(Marca.nombre)))


class SucursalRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, sucursal_id: uuid.UUID) -> Sucursal | None:
        return self.s.scalar(
            select(Sucursal).where(
                Sucursal.id == sucursal_id, Sucursal.deleted_at.is_(None)
            )
        )

    def list(
        self,
        empresa_id: uuid.UUID | None = None,
        marca_id: uuid.UUID | None = None,
    ) -> list[Sucursal]:
        stmt = select(Sucursal).where(Sucursal.deleted_at.is_(None))
        if empresa_id is not None:
            stmt = stmt.where(Sucursal.empresa_id == empresa_id)
        if marca_id is not None:
            stmt = stmt.where(Sucursal.marca_id == marca_id)
        return list(self.s.scalars(stmt.order_by(Sucursal.nombre)))

    def add(self, sucursal: Sucursal) -> Sucursal:
        self.s.add(sucursal)
        self.s.flush()
        return sucursal
