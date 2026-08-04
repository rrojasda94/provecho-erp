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


@dataclass(frozen=True)
class ConsultaPersona:
    """Resultado de consultar un DNI contra Factiliza/RENIEC (RN-PTS-004,
    alta de cliente/trabajador/proveedor natural la primera vez que se ve
    ese documento — `nombres`/`apellidos` separados, mismo formato que
    `Persona`, para no reparsear "nombre completo")."""

    encontrado: bool
    numero_documento: str
    nombres: str
    apellidos: str
    crudo: dict


@dataclass(frozen=True)
class ConsultaEmpresa:
    """Resultado de consultar un RUC contra Factiliza/SUNAT."""

    encontrado: bool
    numero_documento: str
    razon_social: str
    estado: str
    condicion: str
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


def _interpretar_dni(numero: str, cuerpo: dict) -> ConsultaPersona:
    datos = cuerpo.get("data") or {}
    apellidos = " ".join(
        filter(None, [datos.get("apellido_paterno"), datos.get("apellido_materno")])
    )
    return ConsultaPersona(
        encontrado=bool(cuerpo.get("success")) and bool(datos.get("nombres")),
        numero_documento=str(datos.get("numero") or numero),
        nombres=datos.get("nombres") or "",
        apellidos=apellidos,
        crudo=cuerpo,
    )


def _interpretar_ruc(numero: str, cuerpo: dict) -> ConsultaEmpresa:
    datos = cuerpo.get("data") or {}
    return ConsultaEmpresa(
        encontrado=bool(cuerpo.get("success")) and bool(datos.get("nombre_o_razon_social")),
        numero_documento=str(datos.get("numero") or numero),
        razon_social=datos.get("nombre_o_razon_social") or "",
        estado=datos.get("estado") or "",
        condicion=datos.get("condicion") or "",
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
        self.consulta_base_url = settings.factiliza_consulta_base_url.rstrip("/")
        self.token = token if token is not None else settings.factiliza_token
        self.timeout = timeout or settings.factiliza_timeout_segundos

    def enviar_comprobante(self, payload: dict) -> RespuestaEmision:
        """POST /invoice/send — boleta o factura.

        Un rechazo de SUNAT (400) es una respuesta válida del negocio, no
        una excepción: el comprobante queda `rechazado` con el motivo. Solo
        los fallos de transporte levantan `FactilizaError` para que la cola
        reintente.
        """
        return self._enviar("/invoice/send", payload)

    def enviar_nota_credito(self, payload: dict) -> RespuestaEmision:
        """POST /note/send — nota de crédito. Mismo contrato de errores que
        la emisión: rechazo es veredicto, transporte caído es excepción."""
        return self._enviar("/note/send", payload)

    def _enviar(self, ruta: str, payload: dict) -> RespuestaEmision:
        if not self.token:
            raise FactilizaError("FACTILIZA_TOKEN no configurado")
        try:
            respuesta = httpx.post(
                f"{self.base_url}{ruta}",
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

    def _consultar(self, ruta: str, numero: str) -> dict | None:
        """GET de consulta RUC/DNI, contra `consulta_base_url` — producto
        distinto de `invoice/send` (esa es solo emisión, apunta a la QA de
        facturación). Un 404 vacío es "no encontrado", respuesta válida, no
        excepción; solo transporte/servidor caído levanta `FactilizaError`."""
        if not self.token:
            raise FactilizaError("FACTILIZA_TOKEN no configurado")
        try:
            respuesta = httpx.get(
                f"{self.consulta_base_url}/{ruta}/info/{numero}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise FactilizaError(f"Factiliza no responde: {e}") from e
        if respuesta.status_code == 404 and not respuesta.text:
            return None
        if respuesta.status_code >= 500:
            raise FactilizaError(f"Factiliza devolvió {respuesta.status_code}")
        try:
            return respuesta.json()
        except ValueError as e:
            raise FactilizaError(f"Respuesta ilegible de Factiliza: {e}") from e

    def consultar_dni(self, dni: str) -> ConsultaPersona:
        """GET /dni/info/{dni} — RENIEC vía Factiliza."""
        cuerpo = self._consultar("dni", dni)
        if cuerpo is None:
            return ConsultaPersona(False, dni, "", "", {})
        return _interpretar_dni(dni, cuerpo)

    def consultar_ruc(self, ruc: str) -> ConsultaEmpresa:
        """GET /ruc/info/{ruc} — SUNAT vía Factiliza."""
        cuerpo = self._consultar("ruc", ruc)
        if cuerpo is None:
            return ConsultaEmpresa(False, ruc, "", "", "", {})
        return _interpretar_ruc(ruc, cuerpo)


def nombres_desde_dni(dni: str, nombres_tecleado: str, apellidos_tecleado: str) -> tuple[str, str]:
    """Alta con DNI que todavía no existe en `persona`: el nombre lo da
    RENIEC vía Factiliza, no lo tecleado en caja/mostrador (RN-PTS-004
    addendum 2026-08-02). Si Factiliza no responde o no encuentra el
    documento, se usa lo tecleado — el alta nunca se bloquea por un
    proveedor externo caído (mismo criterio que ADR-005)."""
    try:
        consulta = FactilizaClient().consultar_dni(dni)
    except FactilizaError:
        return nombres_tecleado, apellidos_tecleado
    if not consulta.encontrado:
        return nombres_tecleado, apellidos_tecleado
    return consulta.nombres, consulta.apellidos


def razon_social_desde_ruc(ruc: str, razon_social_tecleada: str) -> str:
    """Mismo criterio que `nombres_desde_dni`, para RUC (SUNAT)."""
    try:
        consulta = FactilizaClient().consultar_ruc(ruc)
    except FactilizaError:
        return razon_social_tecleada
    if not consulta.encontrado:
        return razon_social_tecleada
    return consulta.razon_social
