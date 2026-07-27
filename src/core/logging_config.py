"""Logs uniformes y correlacionados.

Tres flujos (`docs/security/security.md`): `app`, `seguridad` y `auditoria`.
El flujo sale del nombre del logger — `provecho.seguridad.login` es flujo
`seguridad` — para no obligar a pasar un parámetro extra en cada llamada.

En producción sale JSON (una línea por evento, listo para un colector);
en local, texto legible. Ambos llevan el `request_id`, que permite pegar
todos los eventos de un mismo request sin tener que adivinar por timestamp.
"""

import json
import logging
import sys
from contextvars import ContextVar

from src.config.settings import settings

FLUJOS = ("app", "seguridad", "auditoria")
RAIZ = "provecho"
# Etiqueta de nuestro handler: al reconfigurar se retira solo el propio y no
# el de otro (pytest, un integrador externo) que esté escuchando el root.
NOMBRE_HANDLER = "provecho"

# Claves que nunca deben aparecer en un log ni viajar a un servicio externo.
# El PIN de un cajero o un token en claro convierten el log en una brecha.
CLAVES_SENSIBLES = frozenset(
    {
        "pin",
        "pin_hash",
        "password",
        "contrasena",
        "contraseña",
        "authorization",
        "token",
        "access_token",
        "refresh_token",
        "jwt_secret",
        "factiliza_token",
        "s3_secret_key",
        "s3_access_key",
        "pgpassword",
        "secret",
        "api_key",
    }
)
REDACTADO = "[redactado]"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
usuario_id_var: ContextVar[str | None] = ContextVar("usuario_id", default=None)

# Atributos propios de LogRecord: lo que no está acá lo puso quien loguea
# vía `extra=` y va al JSON como contexto.
_ATRIBUTOS_ESTANDAR = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


def redactar(valor: object, _profundidad: int = 0) -> object:
    """Reemplaza valores de claves sensibles, recursivamente."""
    if _profundidad > 6:  # ponytail: corta estructuras cíclicas o absurdas
        return valor
    if isinstance(valor, dict):
        return {
            k: (
                REDACTADO
                if isinstance(k, str) and k.lower() in CLAVES_SENSIBLES
                else redactar(v, _profundidad + 1)
            )
            for k, v in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [redactar(v, _profundidad + 1) for v in valor]
    return valor


def flujo_de(nombre_logger: str) -> str:
    partes = nombre_logger.split(".")
    if len(partes) > 1 and partes[0] == RAIZ and partes[1] in FLUJOS:
        return partes[1]
    return "app"


class FormateadorJson(logging.Formatter):
    """Una línea de JSON por evento — formato uniforme para el colector."""

    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": record.levelname,
            "flujo": flujo_de(record.name),
            "logger": record.name,
            "mensaje": record.getMessage(),
            "app": settings.app_name,
            "entorno": settings.environment,
        }
        if (rid := request_id_var.get()) is not None:
            evento["request_id"] = rid
        if (uid := usuario_id_var.get()) is not None:
            evento["usuario_id"] = uid
        contexto = {
            k: v for k, v in record.__dict__.items() if k not in _ATRIBUTOS_ESTANDAR
        }
        if contexto:
            evento["contexto"] = redactar(contexto)
        if record.exc_info:
            evento["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


class FormateadorTexto(logging.Formatter):
    """Legible para desarrollo; incluye el request_id si lo hay."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        rid = request_id_var.get()
        return f"{base} [req={rid}]" if rid else base


def configurar_logging() -> None:
    """Configura el root logger. Idempotente: se puede llamar en el arranque
    de la API, del worker y de los comandos de consola."""
    usar_json = settings.log_json or settings.es_produccion
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(NOMBRE_HANDLER)
    handler.setFormatter(
        FormateadorJson()
        if usar_json
        else FormateadorTexto("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    raiz = logging.getLogger()
    for previo in [h for h in raiz.handlers if h.get_name() == NOMBRE_HANDLER]:
        raiz.removeHandler(previo)
    raiz.addHandler(handler)
    raiz.setLevel(settings.log_level.upper())
    # uvicorn trae sus propios handlers y duplicaría cada línea.
    for ruidoso in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(ruidoso).handlers = []
        logging.getLogger(ruidoso).propagate = True


def logger_seguridad() -> logging.Logger:
    """Flujo `seguridad`: login, bloqueos, permisos denegados, rate limit."""
    return logging.getLogger(f"{RAIZ}.seguridad")
