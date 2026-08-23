"""Cliente HTTP de Factiliza (facturación electrónica ante SUNAT).

Único punto del ERP que habla con la API. El dominio nunca la llama:
recibe el resultado ya traducido a `RespuestaEmision`.
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from src.config.settings import settings


class FactilizaError(RuntimeError):
    """Fallo de transporte o respuesta ilegible. Reintentable."""


# El CDR llega comprimido: es el ZIP que SUNAT firma, no un XML suelto.
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xml": "application/xml",
    "cdr": "application/zip",
}


@dataclass(frozen=True)
class RespuestaEmision:
    aceptado: bool
    # Código de la respuesta de SUNAT ("0" = aceptado); None si no llegó.
    codigo_sunat: str | None
    mensaje: str
    hash: str | None
    crudo: dict


@dataclass(frozen=True)
class DocumentoDescargado:
    """Representación de un comprobante ya emitido: el PDF que se entrega al
    cliente, el XML firmado o el CDR que devolvió SUNAT.

    Se guarda el binario tal cual llega, sin interpretarlo: el XML y el CDR
    son el respaldo legal de la operación y cualquier reescritura los
    invalidaría.
    """

    formato: str  # pdf | xml | cdr
    contenido: bytes
    content_type: str
    nombre_archivo: str


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
    # RENIEC la devuelve según el plan contratado; `None` cuando no viene.
    # Es opcional a propósito: el alta no puede depender de un campo que el
    # proveedor entrega a veces.
    fecha_nacimiento: date | None = None


@dataclass(frozen=True)
class ConsultaEmpresa:
    """Resultado de consultar un RUC contra Factiliza/SUNAT."""

    encontrado: bool
    numero_documento: str
    razon_social: str
    estado: str
    condicion: str
    crudo: dict
    # El domicilio fiscal, ya partido. SUNAT lo devuelve en campos separados
    # y así se guarda: recomponer una dirección y volver a partirla pierde
    # información en cada vuelta.
    direccion: str = ""
    distrito: str = ""
    provincia: str = ""
    departamento: str = ""


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


def _fecha(valor: object) -> date | None:
    """`"12/05/1994"` o `"1994-05-12"` → `date`. Cualquier otra cosa es
    `None`: una fecha que no se entiende no se adivina, se omite — el
    formulario la deja vacía y la teclea quien la tenga delante."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    return None


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
        fecha_nacimiento=_fecha(datos.get("fecha_nacimiento")),
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
        direccion=datos.get("direccion") or "",
        distrito=datos.get("distrito") or "",
        provincia=datos.get("provincia") or "",
        departamento=datos.get("departamento") or "",
    )


class FactilizaClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
        consulta_token: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.factiliza_base_url).rstrip("/")
        self.consulta_base_url = settings.factiliza_consulta_base_url.rstrip("/")
        self.token = token if token is not None else settings.factiliza_token
        # Emisión y consulta son **dos productos con dos credenciales**: el
        # token de emisión devuelve 401 contra `api.factiliza.com` aunque esté
        # vigente. Cae al de emisión solo si no hay uno propio configurado —
        # una cuenta que use el mismo para todo sigue funcionando, y quien no
        # tiene ninguno recibe el error de "no configurado" de siempre.
        self.consulta_token = (
            consulta_token
            if consulta_token is not None
            else (settings.factiliza_consulta_documento_token or self.token)
        )
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

    def enviar_guia_remision(self, payload: dict) -> RespuestaEmision:
        """POST /despatch/send — guía de remisión remitente (GRE).

        Mismo contrato de errores que los otros dos envíos. El camión ya
        salió cuando esto corre: un rechazo se corrige y se reemite, no
        detiene el traslado — la guía impresa es el documento que viaja.
        """
        return self._enviar("/despatch/send", payload)

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
        if not self.consulta_token:
            raise FactilizaError("FACTILIZA_CONSULTA_DOCUMENTO_TOKEN no configurado")
        try:
            respuesta = httpx.get(
                f"{self.consulta_base_url}/{ruta}/info/{numero}",
                headers={"Authorization": f"Bearer {self.consulta_token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise FactilizaError(f"Factiliza no responde: {e}") from e
        if respuesta.status_code == 404 and not respuesta.text:
            return None
        # 401/403 con cuerpo vacío es lo que devuelve el producto de consulta
        # cuando el token no le sirve —revocado, regenerado en el panel, o de
        # otro producto—. Se nombra: sin esto caía en el `.json()` de abajo y
        # el operador leía "respuesta ilegible", que manda a buscar un error
        # de parseo donde lo que hay que revisar es la credencial.
        if respuesta.status_code in (401, 403):
            raise FactilizaError(
                f"Factiliza rechazó el token ({respuesta.status_code}): revisa "
                "FACTILIZA_CONSULTA_DOCUMENTO_TOKEN —es distinto del de "
                "emisión— y que el plan de consultas esté activo"
            )
        if respuesta.status_code >= 500:
            raise FactilizaError(f"Factiliza devolvió {respuesta.status_code}")
        try:
            return respuesta.json()
        except ValueError as e:
            raise FactilizaError(
                f"Respuesta ilegible de Factiliza ({respuesta.status_code}): {e}"
            ) from e

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

    def descargar(
        self, formato: str, tipo_doc: str, serie: str, correlativo: int
    ) -> DocumentoDescargado:
        """`GET /invoice/{pdf|xml|cdr}/{tipo}/{serie}/{correlativo}`.

        El PDF es lo que se le entrega al cliente; el **XML firmado** y el
        **CDR** son el respaldo ante SUNAT y hay que poder recuperarlos años
        después. Se devuelven como bytes sin tocar: reescribir un XML
        firmado lo invalida.

        Un 404 es "todavía no está" —el documento puede seguir en cola— y
        levanta `FactilizaError` para que quien llame lo trate como
        reintentable, igual que un fallo de transporte.
        """
        if formato not in CONTENT_TYPES:
            raise ValueError(f"formato no descargable: {formato}")
        if not self.token:
            raise FactilizaError("FACTILIZA_TOKEN no configurado")
        url = f"{self.base_url}/invoice/{formato}/{tipo_doc}/{serie}/{correlativo}"
        try:
            respuesta = httpx.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise FactilizaError(f"Factiliza no responde: {e}") from e
        if respuesta.status_code != 200:
            raise FactilizaError(
                f"Factiliza devolvió {respuesta.status_code} al pedir el {formato} "
                f"de {serie}-{correlativo}"
            )
        return DocumentoDescargado(
            formato=formato,
            contenido=respuesta.content,
            content_type=CONTENT_TYPES[formato],
            nombre_archivo=f"{serie}-{correlativo:08d}.{formato if formato != 'cdr' else 'zip'}",
        )


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
