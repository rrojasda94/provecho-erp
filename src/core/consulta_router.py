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

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.modules.users.api.deps import require_permission
from src.shared.integrations.factiliza import FactilizaClient, FactilizaError

router = APIRouter(prefix="/consulta", tags=["consulta"])

CONSULTAR = "consulta.documento"


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
    el 500 manda a revisar este servidor, que está bien."""
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        f"No se pudo consultar el documento: {e}",
    )


@router.get("/dni/{numero}", response_model=ConsultaPersonaOut)
def consultar_dni(
    numero: str,
    _=Depends(require_permission(CONSULTAR)),
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
    _=Depends(require_permission(CONSULTAR)),
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
