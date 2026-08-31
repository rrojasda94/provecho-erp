"""El 422 de Pydantic, dicho en español y nombrando el campo.

FastAPI responde la validación de entrada con una **lista** de
`{loc, msg, type}` y el `msg` en inglés. El frontend descartaba `loc` y
concatenaba los `msg`, así que un formulario con tres campos mal cargados
mostraba `"Field required; Field required; Input should be..."`: tres
veces lo mismo y ninguna decía qué campo. Como el cliente **no** replica
`pattern`, `minimum` ni los enums a propósito (docs/roadmap/deuda/
frontend.md), ese texto es el único mensaje de error que ve el usuario
para toda esa clase de fallos.

Acá se traduce a un sobre igual al del resto del ERP —`{"detail": str}`,
`src/core/error_handlers.py`— con un `errores[]` al lado para que el
formulario pueda marcar el input culpable.

La tabla traduce por `type` de Pydantic, que es un código estable, y no
por el texto del `msg`. Un `type` que no esté en la tabla cae al `msg`
crudo: quedar en inglés es mejor que perder el dato.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.shared import etiquetas


class ErrorCampo(BaseModel):
    """Un campo rechazado. `campo` es la ruta dentro del cuerpo; `etiqueta`,
    su nombre en pantalla."""

    campo: str
    etiqueta: str
    mensaje: str


class ErrorValidacion(BaseModel):
    """Sobre de todo 422. `errores` va vacío cuando el 422 no viene de la
    validación de entrada (`PinInvalido`, los `HTTPException(422)` de los
    routers): el sobre es uno solo."""

    detail: str
    errores: list[ErrorCampo] = []


# Primer segmento de `loc`: dice de dónde salió el dato, no cuál es.
_ORIGENES = frozenset({"body", "query", "path", "header", "cookie"})

# `type` de Pydantic → mensaje, formateado con el `ctx` del error.
MENSAJES: dict[str, str] = {
    "missing": "obligatorio",
    "extra_forbidden": "campo no reconocido",
    "json_invalid": "el cuerpo no es JSON válido",
    "greater_than": "debe ser mayor que {gt}",
    "greater_than_equal": "debe ser mayor o igual que {ge}",
    "less_than": "debe ser menor que {lt}",
    "less_than_equal": "debe ser menor o igual que {le}",
    "multiple_of": "debe ser múltiplo de {multiple_of}",
    "string_too_short": "mínimo {min_length} caracteres",
    "string_too_long": "máximo {max_length} caracteres",
    "too_short": "mínimo {min_length} elementos",
    "too_long": "máximo {max_length} elementos",
    "string_pattern_mismatch": "formato no válido",
    "literal_error": "valor no válido: se espera {expected}",
    "enum": "valor no válido: se espera {expected}",
    "string_type": "debe ser texto",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "int_from_float": "debe ser un número entero",
    "float_parsing": "debe ser un número",
    "float_type": "debe ser un número",
    "decimal_parsing": "debe ser un número",
    "decimal_type": "debe ser un número",
    "decimal_max_digits": "máximo {max_digits} dígitos",
    "decimal_max_places": "máximo {decimal_places} decimales",
    "bool_parsing": "debe ser sí o no",
    "bool_type": "debe ser sí o no",
    "uuid_parsing": "identificador no válido",
    "uuid_type": "identificador no válido",
    "date_parsing": "fecha no válida",
    "date_type": "fecha no válida",
    "date_from_datetime_parsing": "fecha no válida",
    "datetime_parsing": "fecha y hora no válidas",
    "datetime_type": "fecha y hora no válidas",
    "datetime_from_date_parsing": "fecha y hora no válidas",
    "time_parsing": "hora no válida",
    "list_type": "debe ser una lista",
    "dict_type": "debe ser un objeto",
    "model_attributes_type": "debe ser un objeto",
}

# Pydantic arma `expected` de un literal/enum con " or " y no lo traduce.
_CONECTOR = (" or ", " o ")

# Prefijo que Pydantic antepone a lo que levanta un `field_validator`
# nuestro — el mensaje que sigue ya está escrito en español.
_PREFIJO_VALUE_ERROR = "Value error, "


def campo_de(loc: tuple[Any, ...]) -> str:
    """Ruta del campo dentro del cuerpo: `("body","items",0,"cantidad")` →
    `items[0].cantidad`. El origen (`body`, `query`, ...) se descarta: dice
    por dónde viajó el dato, no cuál falló."""
    partes = list(loc)
    if partes and partes[0] in _ORIGENES:
        partes = partes[1:]
    texto = ""
    for parte in partes:
        if isinstance(parte, int):
            texto += f"[{parte}]"
        else:
            texto += f".{parte}" if texto else str(parte)
    return texto


def mensaje_de(error: dict[str, Any]) -> str:
    """Traduce un error de Pydantic. Sin entrada en la tabla, devuelve el
    `msg` original antes que inventar un texto que no dice qué pasó."""
    tipo = error.get("type", "")
    crudo = str(error.get("msg", "")).replace(_PREFIJO_VALUE_ERROR, "", 1)
    plantilla = MENSAJES.get(tipo)
    if plantilla is None:
        return crudo
    try:
        return plantilla.format(**(error.get("ctx") or {})).replace(*_CONECTOR)
    except (KeyError, IndexError):
        # `ctx` sin la clave que la plantilla esperaba: pasa si Pydantic
        # cambia el contrato de un `type`. Mejor el texto original que un
        # KeyError dentro del manejador de errores.
        return crudo


def sobre(exc: RequestValidationError) -> dict[str, Any]:
    errores: list[dict[str, str]] = []
    for error in exc.errors():
        # `json_invalid` trae en `loc` la posición del carácter que rompió el
        # parseo, no un campo: no hay nada que nombrar.
        campo = "" if error.get("type") == "json_invalid" else campo_de(tuple(error.get("loc", ())))
        errores.append(
            {
                "campo": campo,
                # Sin campo es el cuerpo entero (JSON mal formado).
                "etiqueta": etiquetas.etiqueta(campo) if campo else "Cuerpo",
                "mensaje": mensaje_de(error),
            }
        )
    detail = "; ".join(
        f"{e['etiqueta']}: {e['mensaje']}" if e["campo"] else e["mensaje"] for e in errores
    )
    return {"detail": detail or "Entrada inválida", "errores": errores}


def registrar(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            sobre(exc), status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )
