"""Contrato de sincronización de `users` hacia el hub de sucursal (ADR-009).

Sin RBAC replicado nadie puede autenticarse en el hub durante un corte, y
un PDV donde nadie puede loguearse no vende: por eso `usuario` viaja con
su `pin_hash` (Argon2id, nunca el PIN). Es la única superficie de la API
que expone un hash de credencial y por eso está detrás de su propio
permiso (`sync.leer`), acotada a los usuarios de esa sucursal, y sale
únicamente hacia el hub que la nube reconoce como suyo.

La organización (grupo/empresa/marca/sucursal/almacén) viaja por necesidad
de integridad referencial: sin esas filas, `venta` y `stock` no tienen a
qué apuntar en la base local del hub.

`token_agente` (ADR-029) **no** viaja: es la credencial de un agente contra
la nube, y quien se autentica en el hub durante un corte es el personal del
local. Replicarla multiplicaría por sucursal las copias de un secreto que
solo sirve del otro lado.
"""

from sqlalchemy import Select, or_, select

from src.core.sync.contratos import AlcanceHub, RecursoSync
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Permiso,
    Persona,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)


def _usuarios_de_la_sucursal(alcance: AlcanceHub) -> Select:
    return select(UsuarioSucursal.usuario_id).where(
        UsuarioSucursal.sucursal_id == alcance.sucursal_id
    )


def _marca_de_la_sucursal(alcance: AlcanceHub) -> Select:
    return select(Sucursal.marca_id).where(Sucursal.id == alcance.sucursal_id)


RECURSOS = (
    RecursoSync(
        nombre="grupo",
        modelo=Grupo,
        campos=("id", "nombre", "updated_at"),
        filtro=lambda q, a: q.where(
            Grupo.id.in_(select(Empresa.grupo_id).where(Empresa.id == a.empresa_id))
        ),
        motivo="Raíz de la organización; `marca` y `cliente` la referencian.",
    ),
    RecursoSync(
        nombre="empresa",
        modelo=Empresa,
        campos=(
            "id",
            "grupo_id",
            "razon_social",
            "ruc",
            "domicilio_fiscal",
            "contacto",
            "tipo",
            "zona_tributaria",
            "config_fiscal",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Empresa.id == a.empresa_id),
        motivo="Tenant raíz: medio de pago, almacén y comprobante cuelgan de acá.",
    ),
    RecursoSync(
        nombre="marca",
        modelo=Marca,
        campos=("id", "grupo_id", "nombre", "tipo", "skins", "updated_at"),
        filtro=lambda q, a: q.where(Marca.id.in_(_marca_de_la_sucursal(a))),
        motivo="Una sucursal opera una sola marca; el PDV usa su branding.",
    ),
    RecursoSync(
        nombre="sucursal",
        modelo=Sucursal,
        campos=(
            "id",
            "marca_id",
            "empresa_id",
            "nombre",
            "direccion",
            "estado",
            "tenencia",
            "horario_atencion",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Sucursal.id == a.sucursal_id),
        motivo="La sucursal del hub: `venta.sucursal_id` apunta acá.",
    ),
    RecursoSync(
        nombre="almacen",
        modelo=Almacen,
        campos=(
            "id",
            "empresa_id",
            "sucursal_id",
            "nombre",
            "tipo",
            "almacen_abastecedor_id",
            "updated_at",
        ),
        # El almacén del local **y su abastecedor**. El central se agregó el
        # 2026-08-07: sin él, el local no puede ni pedirle insumos durante un
        # corte —`crear_solicitud` exige que el abastecedor exista— ni saber
        # de dónde viene el camión que está recibiendo. Su *stock* sigue sin
        # replicarse (`stock` filtra por almacenes de la sucursal): lo que
        # viaja es la ficha del almacén, no cuánto tiene.
        filtro=lambda q, a: q.where(
            or_(
                Almacen.sucursal_id == a.sucursal_id,
                Almacen.id.in_(
                    select(Almacen.almacen_abastecedor_id).where(
                        Almacen.sucursal_id == a.sucursal_id
                    )
                ),
            ),
            Almacen.deleted_at.is_(None),
        ),
        motivo=(
            "El listener de venta descuenta stock contra el almacén del "
            "local; el abastecedor viaja para poder pedirle sin conexión."
        ),
    ),
    RecursoSync(
        nombre="persona",
        modelo=Persona,
        campos=(
            "id",
            "nombres",
            "apellidos",
            "tipo_documento",
            "numero_documento",
            "anonimizado_at",
            "version",
            "updated_at",
        ),
        # Solo las personas del personal de esa sucursal, y sin domicilio,
        # teléfono, email ni fecha de nacimiento: el PDV muestra un nombre,
        # no una ficha. Minimización de datos (Ley 29733) — el hub vive en
        # un local, no en un datacenter.
        filtro=lambda q, a: q.where(
            Persona.id.in_(
                select(Usuario.persona_id).where(
                    Usuario.id.in_(_usuarios_de_la_sucursal(a)),
                    Usuario.persona_id.is_not(None),
                )
            )
        ),
        motivo="`usuario.persona_id` necesita la fila; el PDV muestra el nombre.",
    ),
    RecursoSync(
        nombre="usuario",
        modelo=Usuario,
        campos=(
            "id",
            "username",
            "pin_hash",
            "persona_id",
            "nombre_display",
            "tipo",
            "activo",
            "deleted_at",
            "updated_at",
        ),
        # `intentos_fallidos`/`bloqueado_hasta` NO viajan: el lockout es
        # estado vivo de cada lado. Replicarlo dejaría a un cajero bloqueado
        # en el hub por intentos hechos en la nube, o al revés.
        filtro=lambda q, a: q.where(Usuario.id.in_(_usuarios_de_la_sucursal(a))),
        motivo="Autenticación local durante el corte (RBAC completo offline).",
    ),
    RecursoSync(
        nombre="rol",
        modelo=Rol,
        campos=("id", "nombre", "descripcion", "deleted_at", "updated_at"),
        filtro=lambda q, a: q,
        motivo="Catálogo global y chico; el rol define qué puede hacer el cajero.",
    ),
    RecursoSync(
        nombre="permiso",
        modelo=Permiso,
        campos=("id", "codigo", "descripcion", "restricciones", "deleted_at", "updated_at"),
        filtro=lambda q, a: q,
        motivo="Sin permisos locales, `require_permission` rechaza todo en el hub.",
    ),
    RecursoSync(
        nombre="rol_permiso",
        modelo=RolPermiso,
        campos=("rol_id", "permiso_id", "updated_at"),
        filtro=lambda q, a: q,
        motivo="La asignación rol→permiso que resuelve la autorización local.",
    ),
    RecursoSync(
        nombre="usuario_rol",
        modelo=UsuarioRol,
        campos=("usuario_id", "rol_id", "updated_at"),
        filtro=lambda q, a: q.where(
            UsuarioRol.usuario_id.in_(_usuarios_de_la_sucursal(a))
        ),
        motivo="Qué rol tiene cada usuario del local.",
    ),
    RecursoSync(
        nombre="usuario_sucursal",
        modelo=UsuarioSucursal,
        campos=("usuario_id", "sucursal_id", "updated_at"),
        filtro=lambda q, a: q.where(UsuarioSucursal.sucursal_id == a.sucursal_id),
        motivo="Alcance del usuario; sin la fila, el claim de sucursal sale vacío.",
    ),
)
