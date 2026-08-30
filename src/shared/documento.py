"""Tipo y número de documento de identidad: el vocabulario único del ERP.

Estaba escrito en cuatro sitios que no coincidían —el `Enum` de `persona`, la
tupla de `sales.application.clientes`, y dos listas de `<option>` en el
frontend—, y elegir «RUC» en el alta de persona devolvía 500: SQLAlchemy
rechaza en Python el valor que el formulario ofrecía. Un vocabulario partido no
falla el día que se escribe, falla el día que alguien usa la opción que sobra.

Vive en `shared` y no en `sales/domain/rules.py` porque `users` y `rrhh` no
pueden importar el dominio de otro módulo (CLAUDE.md); `rules` reexporta los
largos desde acá para no volver a tener dos copias.

**RUC de persona natural**: en Perú una persona natural con negocio tiene RUC
(empieza en 10), así que es un tipo legítimo de `persona` y no solo de empresa.
Distinto del `ruc` de `cliente`/`proveedor`/`empresa`, que identifica a una
persona jurídica y tiene columna propia.
"""

DNI = "dni"
CE = "ce"
PASAPORTE = "pasaporte"
RUC = "ruc"

#: Todo lo que `persona.tipo_documento` acepta.
TIPOS = (DNI, CE, PASAPORTE, RUC)

#: Los de una persona natural sin negocio. `sales` distingue: un documento de
#: 11 dígitos hace al cliente **jurídico**, y ese RUC no va en la persona.
NATURALES = (DNI, CE, PASAPORTE)

#: Lo que llega de fuera con otro nombre. El tablero de contratación mandaba
#: `carne_extranjeria` desde que existe, y romper ese formulario para que diga
#: `ce` no le sirve a nadie: se normaliza al entrar.
ALIAS = {
    "carne_extranjeria": CE,
    "carnet_extranjeria": CE,
    "carné_extranjería": CE,
}

LARGO_DNI = 8
LARGO_RUC = 11

#: Los que son un número de largo fijo. CE y pasaporte no: los emite otro país.
LARGO_EXACTO = {DNI: LARGO_DNI, RUC: LARGO_RUC}

#: El de la columna `persona.numero_documento`.
LARGO_MAXIMO = 20
LARGO_MINIMO = 6

ETIQUETA = {
    DNI: "DNI",
    CE: "carné de extranjería",
    PASAPORTE: "pasaporte",
    RUC: "RUC",
}


def normalizar(tipo: str | None) -> str | None:
    """Minúsculas, sin espacios y con los alias resueltos. `None` si viene
    vacío — el documento es opcional desde ADR-018."""
    if tipo is None:
        return None
    limpio = tipo.strip().lower()
    if not limpio:
        return None
    return ALIAS.get(limpio, limpio)


def validar(tipo: str | None, numero: str | None) -> tuple[str | None, str | None]:
    """Devuelve el par ya normalizado, o levanta `ValueError`.

    Sin documento es válido: un cliente de mostrador no siempre lo da
    (ADR-018). Con número **sí** hace falta el tipo, porque es lo que decide
    a qué padrón se consulta y qué se declara a SUNAT.
    """
    tipo = normalizar(tipo)
    numero = (numero or "").strip() or None
    if tipo is not None and tipo not in TIPOS:
        raise ValueError(
            f"tipo de documento inválido: «{tipo}». Debe ser uno de: {', '.join(TIPOS)}"
        )
    if numero is None:
        return tipo, None
    if tipo is None:
        raise ValueError("un número de documento necesita decir de qué tipo es")

    exacto = LARGO_EXACTO.get(tipo)
    if exacto is not None:
        if not numero.isdigit() or len(numero) != exacto:
            raise ValueError(f"un {ETIQUETA[tipo]} son {exacto} dígitos")
    elif not numero.isalnum() or not LARGO_MINIMO <= len(numero) <= LARGO_MAXIMO:
        raise ValueError(
            f"un {ETIQUETA[tipo]} son de {LARGO_MINIMO} a {LARGO_MAXIMO} "
            "caracteres alfanuméricos"
        )
    return tipo, numero
