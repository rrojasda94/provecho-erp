"""Config de Apache Superset para el BI autoservicio (ADR-082 Fase C).

Se monta en `/app/pythonpath/superset_config.py` (docker-compose.bi.yml) —
es el path que la imagen oficial ya trae en `PYTHONPATH`, así que Superset
lo importa solo, sin flag extra.

Todo lo que es secreto sale de variables de entorno (`.env` del droplet BI,
nunca de este archivo, que sí se commitea).
"""

import os

from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager

# --- Identidad del proceso ---------------------------------------------
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# --- Metadata de Superset: esquema aparte de la Postgres de staging -----
# Rol `superset_meta`, creado por `scripts/superset_provision_db.sql` —
# CRUD solo sobre su propio esquema, cero acceso a las tablas de Provecho ni
# a las vistas `vw_bi_*` (eso lo hace el rol `bi_lector`, aparte, cuando se
# registra la conexión analítica desde la UI/`scripts/superset_init.py`).
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_METADATA_DATABASE_URI"]

# --- SSO contra Provecho (OAuth2, ADR-082 Fase B) -----------------------
# `PROVECHO_API_URL` es la API por su dominio público (`/token` y
# `/userinfo` los llama este proceso, servidor-a-servidor — no hay cookie ni
# red privada de por medio, así que no hace falta VPC para esto).
# `PROVECHO_WEB_URL` es el frontend: `/oauth/authorize` vive ahí (ver
# ADR-082 Fase B — la sesión de Provecho es una cookie que la API nunca ve).
PROVECHO_API_URL = os.environ["PROVECHO_API_URL"].rstrip("/")
PROVECHO_WEB_URL = os.environ["PROVECHO_WEB_URL"].rstrip("/")

AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [
    {
        "name": "provecho",
        "icon": "fa-lock",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ["OAUTH_BI_CLIENT_ID"],
            "client_secret": os.environ["OAUTH_BI_CLIENT_SECRET"],
            # Con la barra final: Authlib arma `api_base_url + "userinfo"`.
            "api_base_url": f"{PROVECHO_API_URL}/api/v1/oauth/",
            "access_token_url": f"{PROVECHO_API_URL}/api/v1/oauth/token",
            "authorize_url": f"{PROVECHO_WEB_URL}/oauth/authorize",
            "client_kwargs": {"scope": "profile"},
        },
    }
]

# El primer login crea el usuario en Superset — no hay que darlos de alta a
# mano acá además de en `src/seeders/seed.py` (`bi.acceder`).
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
# Se resincroniza en cada login: si a alguien le quitan `bi.acceder` en
# Provecho, pierde el rol elevado en Superset la próxima vez que entra —
# no hace falta un paso aparte acá.
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    # Superusuario de Provecho (permiso `*`, `src/seeders/seed.py`).
    "admin": ["Admin"],
    "supervisor": ["Gamma", "ProvechoBI"],
    "contador": ["Gamma", "ProvechoBI"],
}


class ProvechoSecurityManager(SupersetSecurityManager):
    """Traduce la respuesta de `GET /oauth/userinfo` (`src/core/oauth/
    router.py`) al formato que Flask-AppBuilder espera de un proveedor
    OAuth genérico. `role_keys` es el campo que `AUTH_ROLES_MAPPING`
    necesita para decidir en qué rol de Superset entra cada quien —
    los nombres de rol de Provecho llegan tal cual devuelve `/userinfo`."""

    def oauth_user_info(self, provider, response=None):
        if provider != "provecho":
            return {}
        datos = self.appbuilder.sm.oauth_remotes[provider].get("userinfo").json()
        return {
            "username": datos["preferred_username"],
            "email": datos.get("email"),
            "first_name": datos.get("name", ""),
            "last_name": "",
            "role_keys": datos.get("roles", []),
        }


CUSTOM_SECURITY_MANAGER = ProvechoSecurityManager

# --- Feature flags -------------------------------------------------------
FEATURE_FLAGS = {
    # Guest tokens para embeber tableros en /dashboard (ADR-082 Fase D).
    "EMBEDDED_SUPERSET": True,
    "DASHBOARD_RBAC": True,
    # Sin esto, `{{ current_username() }}` en la cláusula de RLS
    # (`scripts/superset_init.py`) NO se interpola: queda como texto
    # literal, la comparación de `username` nunca coincide con nadie y la
    # RLS filtra en silencio a cero filas para todo el mundo — sin ningún
    # error que lo delate. Comprobado a mano al ensayar esta fase: con esta
    # flag apagada, `POST /chart/data` respondía 200 y 0 filas siempre.
    "ENABLE_TEMPLATE_PROCESSING": True,
    # `ALERT_REPORTS` deliberadamente AFUERA: pide Celery worker/beat +
    # Chromium headless para el PDF programado, y no entra en el droplet de
    # 1 GB elegido para este volumen de uso (ver ADR-082 "Dónde corre").
}

# Sin Celery (ver ADR-082): sin esto Superset intenta usar el broker por
# defecto y cada intento de caché/async falla contra un Redis que no existe
# en este droplet. `SimpleCache` es en memoria del propio proceso —
# suficiente para el volumen esperado, se pierde al reiniciar el contenedor.
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache"}
DATA_CACHE_CONFIG = CACHE_CONFIG
FILTER_STATE_CACHE_CONFIG = CACHE_CONFIG
EXPLORE_FORM_DATA_CACHE_CONFIG = CACHE_CONFIG

# SQL Lab es la puerta que ningún permiso de fila cierra (ADR-082,
# "Superset con SQL Lab abierto saltea la RLS"). El rol `Gamma` de fábrica
# ya no lo incluye, pero queda como comprobación explícita al primer
# despliegue: entrar como `supervisor`/`contador` y confirmar que "SQL Lab"
# no aparece en el menú. Si aparece, es que `ProvechoBI` (rol propio,
# `scripts/superset_init.py`) se armó con permisos de más.
