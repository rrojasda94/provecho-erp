"""Cuenta de cliente del sitio: registro, login (email/clave o Google),
refresh, logout, perfil, direcciones y favoritos (ADR-104).

Sin JWT del ERP — es la segunda credencial del sistema, completamente
separada. Rate limit por IP en cada endpoint de autenticación, mismo
criterio que `users.api.routers` (login) y `sales.api.publico_routers`
(registro público).
"""

import uuid

from fastapi import APIRouter, Depends

from src.core.rate_limit import rate_limit
from src.modules.storefront.api import cuentas_schemas as schemas
from src.modules.storefront.api.deps import get_cuenta_actual, get_db
from src.modules.storefront.api.error_handlers import http_exception
from src.modules.storefront.application import auth, direcciones, favoritos, recuperacion
from src.modules.storefront.application.errors import (
    CredencialesInvalidas,
    CuentaBloqueada,
    TokenInvalido,
)
from src.modules.storefront.infrastructure.models import StorefrontCuenta
from src.shared import auditoria
from src.shared.ubicacion import CAMPOS as CAMPOS_UBICACION

router = APIRouter(prefix="/storefront/cuentas", tags=["storefront"])

_limite_registro = rate_limit("storefront_cuenta_registro", 10, 3600)
_limite_login = rate_limit("storefront_cuenta_login", 10, 60)
_limite_lectura = rate_limit("storefront_cuenta_lectura", 120, 3600)
# Recuperar clave manda un correo: tope chico por IP para que no sirva de
# ametralladora de correos a un tercero.
_limite_recuperar = rate_limit("storefront_cuenta_recuperar", 5, 3600)


def _ubicacion(body) -> dict:
    return {c: getattr(body, c) for c in CAMPOS_UBICACION}


def _cuenta_out(cuenta: StorefrontCuenta) -> dict:
    return {
        "id": cuenta.id, "email": cuenta.email, "nombres": cuenta.nombres,
        "apellidos": cuenta.apellidos, "tipo_documento": cuenta.tipo_documento,
        "numero_documento": cuenta.numero_documento, "telefono": cuenta.telefono,
        "fecha_nacimiento": cuenta.fecha_nacimiento,
        "tiene_password": cuenta.password_hash is not None,
        "tiene_google": cuenta.google_sub is not None,
        "debe_cambiar_clave": cuenta.debe_cambiar_clave,
    }


@router.post("/registro", response_model=schemas.TokensOut, status_code=201)
def registrar(
    body: schemas.RegistroIn,
    _=Depends(_limite_registro),
    session=Depends(get_db),
):
    tokens = auth.registrar(
        session,
        email=body.email, password=body.password, nombres=body.nombres,
        apellidos=body.apellidos, tipo_documento=body.tipo_documento,
        numero_documento=body.numero_documento, telefono=body.telefono,
        fecha_nacimiento=body.fecha_nacimiento, direccion=body.direccion,
        ubicacion=_ubicacion(body),
    )
    session.commit()
    return tokens


@router.post("/login", response_model=schemas.TokensOut)
def login(
    body: schemas.LoginIn,
    _=Depends(_limite_login),
    session=Depends(get_db),
):
    try:
        tokens = auth.login(session, email=body.email, password=body.password)
    except (CredencialesInvalidas, CuentaBloqueada) as e:
        # Commitear ANTES de fallar: `intentos_fallidos`/`bloqueado_hasta` se
        # perderían con el rollback automático de `get_db` si se dejara caer
        # la excepción al handler global (mismo patrón que `users`).
        session.commit()
        raise http_exception(e) from e
    session.commit()
    return tokens


@router.post("/google", response_model=schemas.TokensOut)
def login_google(
    body: schemas.GoogleLoginIn,
    _=Depends(_limite_login),
    session=Depends(get_db),
):
    tokens = auth.login_google(
        session,
        id_token=body.id_token, nombres=body.nombres, apellidos=body.apellidos,
        tipo_documento=body.tipo_documento, numero_documento=body.numero_documento,
        telefono=body.telefono, fecha_nacimiento=body.fecha_nacimiento,
        direccion=body.direccion, ubicacion=_ubicacion(body),
    )
    session.commit()
    return tokens


@router.post("/refresh", response_model=schemas.TokensOut)
def refresh(
    body: schemas.RefreshIn,
    _=Depends(_limite_login),
    session=Depends(get_db),
):
    try:
        tokens = auth.refresh(session, body.refresh_token)
    except TokenInvalido as e:
        # Commitear ANTES de fallar: un reuso revoca la cadena entera, y esa
        # revocación tiene que sobrevivir aunque el request termine en 401
        # — es la mitigación real, no un efecto secundario descartable.
        session.commit()
        raise http_exception(e) from e
    session.commit()
    return tokens


@router.post("/recuperar", status_code=202)
def recuperar_clave(
    body: schemas.RecuperarIn,
    _=Depends(_limite_recuperar),
    session=Depends(get_db),
):
    """Manda el enlace si el correo tiene cuenta. Siempre responde igual."""
    recuperacion.solicitar_recuperacion(session, email=body.email)
    session.commit()
    return {"ok": True}


@router.post("/restablecer", status_code=204)
def restablecer_clave(
    body: schemas.RestablecerIn,
    _=Depends(_limite_login),
    session=Depends(get_db),
):
    try:
        recuperacion.restablecer_clave(session, token=body.token, password=body.password)
    except TokenInvalido as e:
        raise http_exception(e) from e
    session.commit()


@router.patch("/me/clave", status_code=204)
def cambiar_clave(
    body: schemas.CambiarClaveIn,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    _=Depends(_limite_login),
    session=Depends(get_db),
):
    recuperacion.cambiar_clave(
        session, cuenta=cuenta, clave_actual=body.clave_actual, clave_nueva=body.clave_nueva
    )
    session.commit()


@router.post("/logout", status_code=204)
def logout(
    body: schemas.RefreshIn,
    session=Depends(get_db),
):
    auth.logout(session, body.refresh_token)
    session.commit()


@router.get("/me", response_model=schemas.CuentaOut)
def ver_perfil(
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    _=Depends(_limite_lectura),
):
    return _cuenta_out(cuenta)


@router.patch("/me", response_model=schemas.CuentaOut)
def editar_perfil(
    body: schemas.ActualizarPerfilIn,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    antes = {
        "nombres": cuenta.nombres,
        "apellidos": cuenta.apellidos,
        "telefono": cuenta.telefono,
    }
    if body.nombres is not None:
        cuenta.nombres = body.nombres
    if body.apellidos is not None:
        cuenta.apellidos = body.apellidos
    if body.telefono is not None:
        cuenta.telefono = body.telefono
    # `usuario_id=None`: quien actúa es la propia cuenta del sitio, no un
    # `usuario` del ERP — `entidad_id` identifica cuál cuenta se editó.
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_cuenta",
        entidad_id=cuenta.id,
        accion="editar_perfil",
        datos_antes=antes,
        datos_despues={
            "nombres": cuenta.nombres,
            "apellidos": cuenta.apellidos,
            "telefono": cuenta.telefono,
        },
    )
    session.commit()
    return _cuenta_out(cuenta)


@router.get("/me/ultimo-pedido", response_model=schemas.UltimoPedidoOut | None)
def ultimo_pedido(
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    from src.modules.sales.application.queries_publicas import ultimo_pedido_de_cliente

    if cuenta.cliente_id is None:
        return None
    return ultimo_pedido_de_cliente(session, cuenta.cliente_id)


# --- Direcciones --------------------------------------------------------------
@router.get("/me/direcciones", response_model=list[schemas.DireccionOut])
def listar_direcciones(
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    return direcciones.listar(session, cuenta.id)


@router.post("/me/direcciones", response_model=schemas.DireccionOut, status_code=201)
def crear_direccion(
    body: schemas.DireccionIn,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    direccion = direcciones.crear(
        session, cuenta_id=cuenta.id, etiqueta=body.etiqueta, direccion=body.direccion,
        referencia=body.referencia, predeterminada=body.predeterminada,
        ubicacion=_ubicacion(body),
    )
    session.commit()
    return direccion


@router.patch("/me/direcciones/{direccion_id}", response_model=schemas.DireccionOut)
def editar_direccion(
    direccion_id: uuid.UUID,
    body: schemas.DireccionUpdateIn,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    direccion = direcciones.editar(
        session, cuenta_id=cuenta.id, direccion_id=direccion_id,
        etiqueta=body.etiqueta, direccion=body.direccion, referencia=body.referencia,
        predeterminada=body.predeterminada, ubicacion=_ubicacion(body),
    )
    session.commit()
    return direccion


@router.delete("/me/direcciones/{direccion_id}", status_code=204)
def borrar_direccion(
    direccion_id: uuid.UUID,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    direcciones.borrar(session, cuenta_id=cuenta.id, direccion_id=direccion_id)
    session.commit()


# --- Favoritos ------------------------------------------------------------------
@router.get("/me/favoritos", response_model=list[uuid.UUID])
def listar_favoritos(
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    return favoritos.listar(session, cuenta.id)


@router.post("/me/favoritos", status_code=201)
def agregar_favorito(
    body: schemas.FavoritoIn,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    favoritos.agregar(
        session, cuenta_id=cuenta.id, producto_comercial_id=body.producto_comercial_id
    )
    session.commit()
    return {"ok": True}


@router.delete("/me/favoritos/{producto_comercial_id}", status_code=204)
def quitar_favorito(
    producto_comercial_id: uuid.UUID,
    cuenta: StorefrontCuenta = Depends(get_cuenta_actual),
    session=Depends(get_db),
):
    favoritos.quitar(session, cuenta_id=cuenta.id, producto_comercial_id=producto_comercial_id)
    session.commit()
