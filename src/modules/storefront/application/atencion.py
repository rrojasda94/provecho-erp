"""Atención al cliente sobre las cuentas del sitio (ADR-104): ver quién tiene
cuenta y restablecer la clave de quien no puede recibir un correo.

Lo usa el personal desde el ERP (`/web/clientes`, permisos `storefront.leer` /
`storefront.editar`), nunca el cliente. La clave temporal se muestra **una sola
vez** a quien atiende —no queda guardada en claro— y la cuenta queda obligada a
cambiarla apenas el cliente ingrese.
"""

import secrets
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.modules.storefront.application.errors import NoEncontrado
from src.modules.storefront.application.recuperacion import fijar_clave
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.modules.storefront.infrastructure.repositories import CuentaRepo
from src.shared import auditoria

#: Sin 0/O, 1/l/I ni letras que se confunden al dictarla por teléfono.
ALFABETO_TEMPORAL = "abcdefghjkmnpqrstuvwxyz23456789"
LARGO_TEMPORAL = 8
LIMITE_LISTADO = 100


def clave_temporal() -> str:
    return "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(LARGO_TEMPORAL))


def listar(session: Session, *, q: str | None = None) -> list[StorefrontCuenta]:
    """Las cuentas más recientes, o las que coinciden con `q` en email, nombre,
    teléfono o documento."""
    consulta = select(StorefrontCuenta).where(StorefrontCuenta.deleted_at.is_(None))
    q = (q or "").strip()
    if q:
        patron = f"%{q}%"
        consulta = consulta.where(
            or_(
                StorefrontCuenta.email.ilike(patron),
                StorefrontCuenta.nombres.ilike(patron),
                StorefrontCuenta.apellidos.ilike(patron),
                StorefrontCuenta.telefono.ilike(patron),
                StorefrontCuenta.numero_documento.ilike(patron),
            )
        )
    return list(
        session.scalars(consulta.order_by(StorefrontCuenta.created_at.desc()).limit(LIMITE_LISTADO))
    )


def restablecer_por_atencion(
    session: Session, *, cuenta_id: uuid.UUID, actor_id: uuid.UUID
) -> str:
    cuenta = CuentaRepo(session).get(cuenta_id)
    if cuenta is None or cuenta.deleted_at is not None:
        raise NoEncontrado("cuenta no encontrada")
    clave = clave_temporal()
    fijar_clave(session, cuenta, clave)
    cuenta.debe_cambiar_clave = True
    auditoria.registrar(
        session,
        usuario_id=actor_id,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="restablecer_clave_por_atencion",
        datos_despues={"debe_cambiar_clave": True},
    )
    return clave
