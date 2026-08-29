"""Los campos con que una dirección de texto queda anclada al mapa (ADR-053).

Un solo lugar para los cinco campos y sus validaciones. Los declaran una
docena de schemas repartidos en tres módulos, y repetir el rango de la latitud
doce veces es exactamente cómo el decimotercero queda sin validar.

Espeja `UbicacionMixin` de `src/core/model_base.py`: mismos nombres que las
columnas, para que un `model_dump()` entre directo al constructor de la
entidad sin traducir nada en el medio.
"""

from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from pydantic import BaseModel, Field, model_validator

# Los nombres, para las listas de campos editables de los casos de uso.
CAMPOS: tuple[str, ...] = (
    "ubicacion_place_id",
    "ubicacion_lat",
    "ubicacion_lng",
    "ubicacion_plus_code",
    "ubicacion_distrito",
)


class UbicacionMixin(BaseModel):
    """Para heredar en cualquier schema que acepte o devuelva una dirección.

    **Todo opcional, a propósito.** Una dirección escrita a mano sigue siendo
    válida: hay calles que Google no conoce, y es además lo único que queda
    cuando no hay internet (el hub offline de una sucursal) o cuando la clave
    no está configurada. Exigir coordenadas sería dejar de dar de alta un
    proveedor porque un tercero no contestó.

    Los rangos se validan acá y no en la base porque un CHECK devuelve un 500
    en el flush; esto devuelve un 422 con el nombre del campo.
    """

    ubicacion_place_id: str | None = Field(default=None, max_length=255)
    ubicacion_lat: Decimal | None = Field(default=None, ge=-90, le=90)
    ubicacion_lng: Decimal | None = Field(default=None, ge=-180, le=180)
    ubicacion_plus_code: str | None = Field(default=None, max_length=20)
    ubicacion_distrito: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _la_coordenada_va_completa(self) -> "UbicacionMixin":
        """Media coordenada no es un punto.

        Sin esto una latitud sin longitud entra a la base y no molesta a
        nadie hasta que alguien calcula una distancia de reparto, que es
        donde el error aparece lejísimos de su causa.
        """
        if (self.ubicacion_lat is None) != (self.ubicacion_lng is None):
            raise ValueError(
                "ubicacion_lat y ubicacion_lng van juntas: o las dos o ninguna"
            )
        return self


def desanclar(entidad) -> dict[str, str]:
    """Borra el punto del mapa y devuelve lo que había, para la auditoría."""
    antes = {
        campo: str(getattr(entidad, campo))
        for campo in CAMPOS
        if getattr(entidad, campo) is not None
    }
    for campo in CAMPOS:
        setattr(entidad, campo, None)
    return antes


def desanclar_si_cambio_el_texto(
    entidad, campos: dict, texto_anterior: str | None, campo_texto: str
) -> dict[str, str]:
    """El pin vale para la dirección con la que se eligió, y para ninguna otra.

    Corregir "Jr. Lima 200" por "Jr. Lima 400" sin volver a elegir en el mapa
    dejaría las coordenadas de la puerta vieja: el texto diría una calle y el
    reparto iría a otra, cobrando la distancia equivocada. Ante la duda se
    pierde el pin, que se vuelve a poner en dos clicks, y no la verdad.

    No alcanza con `_aplicar` ignorando los `None` (la convención de PATCH de
    este ERP, donde ausente = no tocar): justamente por esa convención un
    formulario que corrige el texto sin ancla nueva no puede pedir el borrado.
    """
    texto_nuevo = campos.get(campo_texto)
    if texto_nuevo is None or texto_nuevo == texto_anterior:
        return {}
    if campos.get("ubicacion_place_id"):
        return {}
    return desanclar(entidad)


_RADIO_TIERRA_M = 6_371_000


def metros_entre(lat1: Decimal, lng1: Decimal, lat2: Decimal, lng2: Decimal) -> int:
    """Distancia en línea recta entre dos puntos (Haversine), en metros.

    No es `distancia_km` de `shared/integrations/google/rutas.py`: esa llama
    a la Routes API por red y mide manejando, para cotizar delivery. Esto es
    local, sin red, y mide en línea recta — lo que hace falta para saber si
    un marcaje ocurrió cerca de la sucursal, no cuánto tardaría en llegar.
    """
    la1, lo1, la2, lo2 = (radians(float(v)) for v in (lat1, lng1, lat2, lng2))
    dlat, dlng = la2 - la1, lo2 - lo1
    a = sin(dlat / 2) ** 2 + cos(la1) * cos(la2) * sin(dlng / 2) ** 2
    return round(2 * _RADIO_TIERRA_M * asin(sqrt(a)))

