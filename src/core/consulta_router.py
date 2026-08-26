"""Consulta de DNI y RUC contra Factiliza (RENIEC/SUNAT), para prellenar altas.

Vive en `core` por lo mismo que el `audit_log`: no tiene dueño de módulo. El
mismo documento lo teclean `users` al dar de alta una persona, `purchases` al
registrar un proveedor y `sales` al identificar a un cliente en caja, y las
tres pantallas hacen la misma pregunta a la misma integración.

**Prellena, no decide.** Lo que devuelve se escribe en un formulario que el
usuario todavía puede corregir. Si Factiliza no responde, el alta sigue
siendo posible tecleando — mismo criterio que ADR-005 y que los helpers
`nombres_desde_dni` / `razon_social_desde_ruc`, que ya aplican el dato en el
servidor al momento de crear.

Solo lectura: acá no se guarda nada.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.config.settings import settings
from src.core.rate_limit import consumir, ip_de
from src.modules.users.api.deps import require_permission
from src.shared.integrations.factiliza import FactilizaClient, FactilizaError

log = logging.getLogger("provecho.app")

router = APIRouter(prefix="/consulta", tags=["consulta"])

CONSULTAR = "consulta.documento"

# Una sola instancia y no `require_permission(CONSULTAR)` en cada endpoint:
# FastAPI cachea el resultado de una dependencia **por objeto llamable**, y la
# factory devuelve uno nuevo en cada llamada. Compartirlo es lo que hace que
# los permisos se resuelvan una vez por request y no dos.
_exigir_permiso = require_permission(CONSULTAR)


def _con_cuota(request: Request, usuario=Depends(_exigir_permiso)):
    """Permiso + cuota. Lo que se cuida acá es el **gasto**: cada consulta
    vale una llamada a un proveedor pago (ADR-041).

    Se cuenta por usuario **y** por IP porque ninguna de las dos alcanza sola.
    Solo por IP, un local con cuatro cajas comparte una cuota y el cajero que
    se pasa deja sin consultar a los otros tres; solo por usuario, nada frena
    a quien tenga varias cuentas a mano.

    El usuario primero: es el límite angosto y el que identifica a quien se
    está pasando, y cortarlo ahí evita que además le queme al local la cuota
    compartida. Va **después** de `require_permission` a propósito — a quien
    no puede consultar no hay que contarle nada, porque su 403 no le cuesta
    un centavo a nadie.
    """
    ventana = settings.consulta_documento_ventana_segundos
    consumir(
        "consulta_usuario",
        str(usuario.id),
        settings.consulta_documento_intentos_usuario,
        ventana,
    )
    consumir(
        "consulta_ip",
        ip_de(request),
        settings.consulta_documento_intentos_ip,
        ventana,
    )
    return usuario


class ConsultaPersonaOut(BaseModel):
    """Lo que se puede prellenar de una persona natural. Sin `crudo`: la
    respuesta completa del proveedor trae más datos personales de los que
    esta pantalla necesita, y lo que no se manda no se filtra (Ley 29733)."""

    encontrado: bool
    numero_documento: str
    nombres: str
    apellidos: str
    fecha_nacimiento: date | None = None


class ConsultaEmpresaOut(BaseModel):
    encontrado: bool
    numero_documento: str
    razon_social: str
    # Estado y condición ante SUNAT: un proveedor "BAJA DE OFICIO" o "NO
    # HABIDO" se puede registrar igual, pero quien lo registra tiene que
    # verlo antes de emitirle una orden de compra.
    estado: str
    condicion: str
    direccion: str
    distrito: str
    provincia: str
    departamento: str


def _sin_proveedor(e: FactilizaError) -> HTTPException:
    """502 y no 500: el que falló es un tercero, y la diferencia importa —
    el 500 manda a revisar este servidor, que está bien.

    El motivo real va al log y **no** al cuerpo de la respuesta: trae nombres
    de variables de entorno, el WhatsApp de soporte de Factiliza o el estado
    de la cuenta. Quien lo lee es quien administra el servidor, no el cajero
    que tiene un cliente esperando —a él le sirve saber que teclee y siga—.
    """
    log.warning("consulta de documento fallida: %s", e)
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        "No se pudo consultar el documento. Completa los datos a mano.",
    )


@router.get("/dni/{numero}", response_model=ConsultaPersonaOut)
def consultar_dni(
    numero: str,
    _=Depends(_con_cuota),
):
    if not (numero.isdigit() and len(numero) == 8):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "el DNI son 8 dígitos"
        )
    try:
        consulta = FactilizaClient().consultar_dni(numero)
    except FactilizaError as e:
        raise _sin_proveedor(e) from e
    # "No encontrado" es una respuesta válida y no un 404: el documento puede
    # no estar en RENIEC y el alta seguir adelante tecleando el nombre.
    return ConsultaPersonaOut(
        encontrado=consulta.encontrado,
        numero_documento=consulta.numero_documento,
        nombres=consulta.nombres,
        apellidos=consulta.apellidos,
        fecha_nacimiento=consulta.fecha_nacimiento,
    )


@router.get("/ruc/{numero}", response_model=ConsultaEmpresaOut)
def consultar_ruc(
    numero: str,
    _=Depends(_con_cuota),
):
    if not (numero.isdigit() and len(numero) == 11):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "el RUC son 11 dígitos"
        )
    try:
        consulta = FactilizaClient().consultar_ruc(numero)
    except FactilizaError as e:
        raise _sin_proveedor(e) from e
    return ConsultaEmpresaOut(
        encontrado=consulta.encontrado,
        numero_documento=consulta.numero_documento,
        razon_social=consulta.razon_social,
        estado=consulta.estado,
        condicion=consulta.condicion,
        direccion=consulta.direccion,
        distrito=consulta.distrito,
        provincia=consulta.provincia,
        departamento=consulta.departamento,
    )
