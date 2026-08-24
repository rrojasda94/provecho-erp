"""Landing «Queremos RE-conocerte»: registro de cliente **sin cuenta**.

El cliente del restaurante escanea un QR en la mesa y llega acá desde su
teléfono. No es usuario del ERP y nunca va a serlo, así que esta es la
segunda superficie del sistema sin JWT (la primera es la encuesta de
`marketing`) y se rige por lo mismo: **escribe, no borra, y lee lo mínimo**.

Qué significa «lo mínimo» acá, en concreto:

- No hay ningún `DELETE`. La baja de datos es un derecho ARCO y se atiende
  por el correo de los términos, con la anonimización de `persona` que ya
  existe (ADR-011) — nunca desde una página abierta a internet.
- La única consulta devuelve `{"registrado": true|false}`. Ni el nombre, ni
  el teléfono, ni la fecha del cupón: con más que eso, el endpoint sería un
  buscador del padrón para cualquiera que sepa un DNI.
- El `grupo_id` sale de la promoción activa y jamás del request. Uno que
  viniera de afuera sería permiso para escribir en otro tenant.

El código del cupón **es el DNI** (decisión del usuario, ADR-061): que la
respuesta lo repita no filtra nada, porque es el número que quien pregunta
acaba de teclear.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.rate_limit import rate_limit
from src.modules.sales.api import schemas
from src.modules.sales.application import cupones
from src.modules.users.api.deps import get_db
from src.shared.integrations.factiliza import nombres_desde_dni
from src.shared.ubicacion import CAMPOS as CAMPOS_UBICACION

router = APIRouter(prefix="/sales/publico", tags=["sales"])

# Escribir en el padrón: apretado, porque cada request puede crear una
# `persona`. Diez por hora y por IP alcanzan de sobra para una familia
# registrándose en la misma mesa detrás del mismo NAT.
_limite_registro = rate_limit("reconocerte_registro", 10, 3600)

# Solo lee un booleano, así que puede ser más holgado.
_limite_consulta = rate_limit("reconocerte_consulta", 20, 3600)

# El más duro de los tres, y el que más importa: es el único que convierte
# un DNI en un nombre. Sin este techo, la landing sería un padrón de RENIEC
# consultable a discreción y gratis (ver ADR-061 → «lo que se acepta»).
_limite_nombre = rate_limit("reconocerte_dni", 5, 3600)


@router.get(
    "/reconocerte/promocion", response_model=schemas.PromocionPublicaOut
)
def ver_promocion(
    _=Depends(_limite_consulta),
    session: Session = Depends(get_db),
):
    """Si la campaña sigue viva y con qué descuento.

    La landing pregunta esto antes de dibujar el formulario: la empresa se
    reserva el derecho de terminar la promoción en cualquier momento, y
    dejar que el cliente llene seis campos para recién ahí decirle que no
    hay nada sería la peor forma de contárselo.
    """
    promocion = cupones.promocion_vigente(session)
    return {
        "nombre": promocion.nombre,
        "descuento_porcentaje": promocion.descuento_porcentaje,
        "vigente_hasta": promocion.vigente_hasta,
        "vigencia_cupon_dias": promocion.vigencia_cupon_dias,
    }


@router.post("/reconocerte/consulta", response_model=schemas.ConsultaPublicaOut)
def consultar(
    body: schemas.ConsultaPublicaIn,
    _=Depends(_limite_consulta),
    session: Session = Depends(get_db),
):
    return {
        "registrado": cupones.esta_registrado(
            session,
            numero_documento=body.numero_documento or "",
            telefono=body.telefono or "",
        )
    }


@router.get(
    "/reconocerte/dni/{numero_documento}/nombre",
    response_model=schemas.NombrePublicoOut,
)
def nombre_de_dni(
    numero_documento: str,
    _=Depends(_limite_nombre),
    session: Session = Depends(get_db),
):
    """El nombre de RENIEC, para que el cliente confirme que es él.

    Devuelve vacío —y no un error— cuando el proveedor no contesta o no
    está configurado: el formulario deja escribirlo a mano y el registro
    sigue (RN-PTS-004). Un 502 acá dejaría al cliente parado frente a un
    formulario que no puede completar por algo que no es asunto suyo.
    """
    numero_documento = numero_documento.strip()
    if len(numero_documento) != 8 or not numero_documento.isdigit():
        return {"nombres": "", "apellidos": ""}
    nombres, apellidos = nombres_desde_dni(numero_documento, "", "")
    return {"nombres": nombres, "apellidos": apellidos}


@router.post(
    "/reconocerte/registro",
    response_model=schemas.CuponPublicoOut,
    status_code=201,
)
def registrar(
    body: schemas.RegistroPublicoIn,
    _=Depends(_limite_registro),
    session: Session = Depends(get_db),
):
    """Registra al cliente (si hace falta) y le entrega su cupón.

    Commitea acá y no en el caso de uso, como todo router del módulo. Si
    algo falla antes, `get_db` revierte y el cliente ve el error real: la
    página tiene que poder decirle si su registro entró o no, y un cupón
    mostrado sobre una transacción que se cayó sería la peor respuesta
    posible.
    """
    ubicacion = {campo: getattr(body, campo) for campo in CAMPOS_UBICACION}
    cupon, ya_estaba = cupones.registrar_y_emitir(
        session,
        numero_documento=body.numero_documento,
        nombre=body.nombre,
        telefono=body.telefono,
        fecha_nacimiento=body.fecha_nacimiento,
        direccion=body.direccion,
        ubicacion=ubicacion,
    )
    promocion = cupones.promocion_vigente(session)
    session.commit()
    return {
        "codigo": cupon.codigo,
        "vigente_hasta": cupon.vigente_hasta,
        "descuento_porcentaje": promocion.descuento_porcentaje,
        "ya_estaba_registrado": ya_estaba,
    }
