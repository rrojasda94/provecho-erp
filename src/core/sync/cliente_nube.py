"""Cliente HTTP del hub contra la API de la nube (ADR-009).

El hub es un cliente más de la API pública: se autentica con `/auth/login`
usando su cuenta de servicio (`usuario.tipo=agente_ia`, una por sucursal)
y llama endpoints normales. No hay canal privilegiado ni acceso directo a
la base de la nube — esa fue justamente la alternativa descartada en el ADR.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from src.config.settings import settings

log = logging.getLogger("provecho.sync")

TIMEOUT_SEGUNDOS = 30.0
PREFIJO_API = "/api/v1"


class ErrorNube(Exception):
    """La nube respondió mal (o no respondió). El ciclo la trata como
    'todavía no': el hub sigue vendiendo y reintenta al siguiente."""


class ClienteNube:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        pin: str | None = None,
        cliente_http: httpx.Client | None = None,
    ) -> None:
        self._base = (base_url or settings.cloud_sync_url).rstrip("/")
        self._username = username or settings.cloud_sync_username
        self._pin = pin or settings.cloud_sync_pin
        self._http = cliente_http or httpx.Client(timeout=TIMEOUT_SEGUNDOS)
        self._token: str | None = None

    # --- Autenticación ------------------------------------------------------
    def _login(self) -> None:
        try:
            respuesta = self._http.post(
                f"{self._base}{PREFIJO_API}/auth/login",
                json={"username": self._username, "pin": self._pin},
            )
            respuesta.raise_for_status()
        except httpx.HTTPError as e:
            raise ErrorNube(f"login del hub rechazado: {e}") from e
        self._token = respuesta.json()["access_token"]
        log.info("Hub autenticado contra la nube como %s", self._username)

    def _pedir(self, metodo: str, ruta: str, **kwargs: Any) -> dict:
        """Un reintento tras 401: el access token dura minutos y el ciclo
        de sync corre por horas — que expire es lo normal, no un error."""
        if self._token is None:
            self._login()
        for intento in (1, 2):
            try:
                respuesta = self._http.request(
                    metodo,
                    f"{self._base}{PREFIJO_API}{ruta}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    **kwargs,
                )
            except httpx.HTTPError as e:
                raise ErrorNube(f"{metodo} {ruta}: {e}") from e
            if respuesta.status_code == httpx.codes.UNAUTHORIZED and intento == 1:
                self._login()
                continue
            if respuesta.is_error:
                raise ErrorNube(
                    f"{metodo} {ruta} → {respuesta.status_code}: {respuesta.text[:200]}"
                )
            return respuesta.json()
        raise ErrorNube(f"{metodo} {ruta}: autenticación imposible")

    # --- Operaciones del sync -----------------------------------------------
    def pull(self, recurso: str, desde: datetime | None, limite: int) -> dict:
        params: dict[str, Any] = {"recurso": recurso, "limite": limite}
        if desde is not None:
            params["desde"] = desde.isoformat()
        return self._pedir("GET", "/sync/pull", params=params)

    def push(self, lote: dict) -> dict:
        return self._pedir("POST", "/sync/push", json={"sales": lote})

    def cerrar(self) -> None:
        self._http.close()
