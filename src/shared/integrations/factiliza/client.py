"""Cliente HTTP de Factiliza (facturación electrónica ante SUNAT).

Único punto del ERP que habla con la API. El dominio nunca la llama:
recibe el resultado ya traducido a `RespuestaEmision`.
"""

from dataclasses import dataclass

import httpx

from src.config.settings import settings


class FactilizaError(RuntimeError):
    """Fallo de transporte o respuesta ilegible. Reintentable."""


@dataclass(frozen=True)
class RespuestaEmision:
    aceptado: bool
    # Código de la respuesta de SUNAT ("0" = aceptado); None si no llegó.
    codigo_sunat: str | None
    mensaje: str
    hash: str | None
    crudo: dict


def _interpretar(cuerpo: dict) -> RespuestaEmision:
    datos = cuerpo.get("data") or {}
    sunat = datos.get("sunatResponse") or {}
    cdr = sunat.get("cdrResponse") or {}
    return RespuestaEmision(
        aceptado=bool(cuerpo.get("success")) and bool(sunat.get("success", True)),
        codigo_sunat=cdr.get("code"),
        mensaje=cdr.get("description") or cuerpo.get("message") or "",
        hash=datos.get("hash"),
        crudo=cuerpo,
    )


class FactilizaClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.factiliza_base_url).rstrip("/")
        self.token = token if token is not None else settings.factiliza_token
        self.timeout = timeout or settings.factiliza_timeout_segundos

    def enviar_comprobante(self, payload: dict) -> RespuestaEmision:
        """POST /invoice/send — boleta o factura.

        Un rechazo de SUNAT (400) es una respuesta válida del negocio, no
        una excepción: el comprobante queda `rechazado` con el motivo. Solo
        los fallos de transporte levantan `FactilizaError` para que la cola
        reintente.
        """
        if not self.token:
            raise FactilizaError("FACTILIZA_TOKEN no configurado")
        try:
            respuesta = httpx.post(
                f"{self.base_url}/invoice/send",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
            cuerpo = respuesta.json()
        except httpx.HTTPError as e:
            raise FactilizaError(f"Factiliza no responde: {e}") from e
        except ValueError as e:
            raise FactilizaError(f"Respuesta ilegible de Factiliza: {e}") from e
        if respuesta.status_code >= 500:
            raise FactilizaError(f"Factiliza devolvió {respuesta.status_code}")
        return _interpretar(cuerpo)
