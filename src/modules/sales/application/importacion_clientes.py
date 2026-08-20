"""El padrón de clientes se baja, se edita en Excel y se vuelve a subir
(RN-PTS-007, ADR-051).

Mismo recorrido que el recetario y el catálogo: `exportar` da la plantilla con
los datos adentro, `validar` dice qué entra y qué no **sin guardar nada**, y
`importar` revalida lo que la pantalla confirmó.

**El cliente es del grupo, no de la empresa** (RN-PTS-001): el `grupo_id` se
deriva de la empresa del token y nunca llega desde el request.

**No se consulta a Factiliza.** `crear_cliente` de a uno pregunta a SUNAT o
RENIEC por el nombre; trescientas filas serían trescientas llamadas externas
secuenciales dentro de un solo request, contra una cuota. La planilla manda
sobre el nombre, y SUNAT vuelve a mandar cuando el cliente se edita de a uno.

**De un cliente natural solo se completa el documento.** El nombre, el
teléfono y el domicilio viven en su `persona` (RN-GEN-007, fuente única) y
`sales` no puede escribirla. Una fila que los cambie **se reporta** —"se
corrige en Personas"— en vez de aplicarse a medias o callarse.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.sales.application import clientes as clientes_uc
from src.modules.sales.application.errors import AppError, ReglaNegocio
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Cliente
from src.modules.users.infrastructure.models import Persona
from src.shared import planilla

HOJA_CLIENTES = "Clientes"
HOJA_INSTRUCCIONES = "Instrucciones"

CABECERA_CLIENTES = (
    "ID",
    "Tipo",
    "Nombre / Razón social",
    "Tipo de documento",
    "Número de documento",
    "Teléfono",
    "Email",
    "Dirección / contacto",
    "Fecha de nacimiento",
)

LARGO_NOMBRE = 255
"""Igual que `cliente.razon_social`. Se valida acá porque SQLite no aplica el
largo de un VARCHAR y la fila pasaría en verde para reventar contra Postgres."""


# --- Plantilla y export -------------------------------------------------------
def plantilla() -> bytes:
    """El archivo que se ofrece cuando todavía no hay padrón que exportar."""
    return _libro(
        [
            ["", "natural", "Ana Quispe", "dni", "40404040", "987654321", "",
             "Jr. Lima 100", ""],
            ["", "juridico", "Inversiones Perú SAC", "ruc", "20481234567", "", "",
             "Av. Grau 55", ""],
        ]
    )


def exportar(session: Session, *, grupo_id: uuid.UUID) -> bytes:
    """El padrón del grupo en el formato que `validar` sabe leer."""
    clientes = list(
        session.scalars(
            select(Cliente).where(
                Cliente.grupo_id == grupo_id, Cliente.deleted_at.is_(None)
            )
        )
    )
    personas = {}
    ids = [c.persona_id for c in clientes if c.persona_id]
    if ids:
        personas = {
            p.id: p for p in session.scalars(select(Persona).where(Persona.id.in_(ids)))
        }
    filas = [_fila_export(c, personas.get(c.persona_id)) for c in clientes]
    return _libro(sorted(filas, key=lambda f: f[2].lower()))


def _fila_export(cliente: Cliente, persona: Persona | None) -> list:
    if cliente.tipo == "juridico":
        return [
            str(cliente.id),
            "juridico",
            cliente.razon_social or "",
            "ruc",
            cliente.ruc or "",
            "",
            "",
            # Una sola columna de contacto, igual que la que la pantalla ya
            # muestra: dos columnas darían un round-trip con pérdida.
            cliente.contacto or "",
            "",
        ]
    return [
        str(cliente.id),
        "natural",
        _nombre(persona),
        persona.tipo_documento if persona and persona.tipo_documento else "",
        persona.numero_documento if persona and persona.numero_documento else "",
        persona.telefono if persona else "",
        persona.email if persona else "",
        persona.domicilio if persona else "",
        str(persona.fecha_nacimiento) if persona and persona.fecha_nacimiento else "",
    ]


def _nombre(persona: Persona | None) -> str:
    if persona is None:
        return ""
    return f"{persona.nombres} {persona.apellidos}".strip()


def _libro(clientes: list[list]) -> bytes:
    return planilla.escribir(
        {
            HOJA_CLIENTES: [list(CABECERA_CLIENTES), *clientes],
            HOJA_INSTRUCCIONES: [[linea] for linea in _INSTRUCCIONES],
        }
    )


_INSTRUCCIONES = (
    "Cómo llenar esta plantilla",
    "",
    "Hoja «Clientes»: una fila por cliente.",
    "  · ID: no se toca. Si viene lleno, esa fila ACTUALIZA ese cliente.",
    "  · Tipo: se calcula solo, no se declara — un documento de 11 dígitos es",
    "    un RUC y hace al cliente jurídico. Se exporta para que se lea.",
    "  · Nombre / Razón social: obligatorio.",
    "  · Tipo de documento: dni, ce, pasaporte o ruc.",
    "  · Número de documento: 8 dígitos (DNI) u 11 (RUC). Sirve de identidad",
    "    cuando el ID va vacío. Un cliente sin documento necesita teléfono.",
    "  · Teléfono: obligatorio para un cliente natural sin documento.",
    "  · Dirección / contacto: el domicilio de la persona o el contacto de la",
    "    empresa, según el tipo.",
    "",
    "De un cliente natural que YA EXISTE solo se puede completar el documento:",
    "el nombre, el teléfono y la dirección viven en su ficha de Personas y se",
    "corrigen desde ahí. Si los cambias en la planilla, la fila te lo dice.",
    "",
    "El nombre se toma tal cual: esta carga NO consulta a SUNAT ni a RENIEC.",
    "Nada se guarda hasta que revises el resultado y confirmes.",
)


# --- Fase 1: validar ----------------------------------------------------------
def validar(session: Session, *, grupo_id: uuid.UUID, contenido: bytes) -> dict:
    """Parsea el archivo y dice qué entra, qué actualiza y qué no."""
    libro = planilla.abrir(contenido, requeridas=(HOJA_CLIENTES,))
    filas = _leer(libro)

    del_grupo = list(
        session.scalars(
            select(Cliente).where(
                Cliente.grupo_id == grupo_id, Cliente.deleted_at.is_(None)
            )
        )
    )
    personas = _personas(session, del_grupo)
    por_id = {c.id: c for c in del_grupo}
    por_documento = {
        doc: c for c, doc in ((c, _documento(c, personas)) for c in del_grupo) if doc
    }
    repetidos = _repetidos(filas)

    clientes = [
        _revisar(fila, por_id, por_documento, personas, repetidos) for fila in filas
    ]
    return {
        "clientes": clientes,
        "listas": sum(
            1 for c in clientes if not c["problemas"] and c["accion"] == "crear"
        ),
        "a_actualizar": sum(
            1 for c in clientes if not c["problemas"] and c["accion"] == "actualizar"
        ),
        "con_problema": sum(1 for c in clientes if c["problemas"]),
    }


def _revisar(fila, por_id, por_documento, personas, repetidos) -> dict:
    documento = fila["documento"]
    accion, existente, problemas = _identidad(fila, por_id, por_documento, repetidos)

    nombre = fila["nombre"]
    if not nombre:
        problemas.append("el nombre o la razón social es obligatorio")
    elif not planilla.largo_ok(nombre, LARGO_NOMBRE):
        problemas.append(f"el nombre supera los {LARGO_NOMBRE} caracteres")

    if documento and not rules.documento_receptor_valido(documento):
        problemas.append(
            f"el documento «{documento}» debe tener 8 dígitos (DNI) u 11 (RUC)"
        )
    tipo = _tipo(documento)
    if existente is None and tipo == "natural" and not fila["telefono"]:
        # El teléfono sustituye al documento como forma de encontrarlo
        # después. Sin ninguno de los dos el registro no sirve para nada.
        if not rules.cliente_identificado(documento):
            problemas.append("un cliente sin documento necesita teléfono")

    fecha = planilla.a_fecha(fila["nacimiento"])
    if fila["nacimiento"] and fecha is None:
        problemas.append(f"fecha de nacimiento inválida: «{fila['nacimiento']}»")

    cambios, no_editables = (
        _diferencias(existente, personas, fila) if existente else ([], [])
    )
    problemas += no_editables

    return {
        "fila": fila["fila"],
        "id": str(fila["id"]) if fila["id"] else (str(existente.id) if existente else None),
        "accion": accion,
        "tipo": existente.tipo if existente else tipo,
        "nombre": nombre,
        "tipo_documento": fila["tipo_documento"] or ("ruc" if tipo == "juridico" else "dni"),
        "documento": documento,
        "telefono": fila["telefono"],
        "email": fila["email"],
        "contacto": fila["contacto"],
        "fecha_nacimiento": str(fecha) if fecha else None,
        "cambios": cambios,
        "problemas": problemas,
    }


def _identidad(fila, por_id, por_documento, repetidos):
    """Quién es esta fila: `ID` si vino, si no el número de documento."""
    problemas: list[str] = []
    existente = None
    accion = "crear"

    if fila["id"]:
        # Una fila con ID pide actualizar, resuelva o no: degradarla a alta
        # convertiría un ID mal pegado en un cliente duplicado, en silencio.
        accion = "actualizar"
        if fila["id"] in repetidos["ids"]:
            problemas.append("el mismo ID aparece en más de una fila")
        existente = por_id.get(fila["id"])
        if existente is None:
            problemas.append("el ID no corresponde a ningún cliente del grupo")
        return accion, existente, problemas

    documento = fila["documento"]
    if documento and documento in repetidos["documentos"]:
        problemas.append("el mismo documento aparece en más de una fila")
    if documento:
        existente = por_documento.get(documento)
        if existente is not None:
            accion = "actualizar"
    return accion, existente, problemas


def _diferencias(cliente: Cliente, personas, fila) -> tuple[list[str], list[str]]:
    """Qué cambia, y qué de eso este módulo no puede escribir."""
    cambios, no_editables = [], []
    if cliente.tipo == "juridico":
        if fila["nombre"] and fila["nombre"] != (cliente.razon_social or ""):
            cambios.append(f"razón social: {cliente.razon_social} → {fila['nombre']}")
        if fila["documento"] and fila["documento"] != (cliente.ruc or ""):
            cambios.append(f"RUC: {cliente.ruc} → {fila['documento']}")
        if fila["contacto"] and fila["contacto"] != (cliente.contacto or ""):
            cambios.append("contacto")
        return cambios, no_editables

    persona = personas.get(cliente.persona_id)
    actual = _nombre(persona)
    if fila["nombre"] and persona and fila["nombre"] != actual:
        no_editables.append(
            f"el nombre de «{actual}» se corrige en Personas, no por planilla "
            "(RN-GEN-007)"
        )
    for campo, valor, etiqueta in (
        ("telefono", fila["telefono"], "el teléfono"),
        ("email", fila["email"], "el email"),
        ("domicilio", fila["contacto"], "la dirección"),
    ):
        if valor and persona and valor != (getattr(persona, campo) or ""):
            no_editables.append(f"{etiqueta} se corrige en Personas (RN-GEN-007)")
    if fila["documento"] and fila["documento"] != (
        persona.numero_documento if persona else None
    ):
        cambios.append(f"documento: → {fila['documento']}")
    return cambios, no_editables


def _tipo(documento: str) -> str:
    return "juridico" if len(documento) == rules.LARGO_RUC else "natural"


def _documento(cliente: Cliente, personas) -> str | None:
    if cliente.tipo == "juridico":
        return cliente.ruc
    persona = personas.get(cliente.persona_id)
    return persona.numero_documento if persona else None


def _personas(session: Session, clientes: list[Cliente]) -> dict:
    ids = [c.persona_id for c in clientes if c.persona_id]
    if not ids:
        return {}
    return {p.id: p for p in session.scalars(select(Persona).where(Persona.id.in_(ids)))}


def _repetidos(filas: list[dict]) -> dict[str, set]:
    ids = [f["id"] for f in filas if f["id"]]
    docs = [f["documento"] for f in filas if f["documento"]]
    return {
        "ids": {i for i in ids if ids.count(i) > 1},
        "documentos": {d for d in docs if docs.count(d) > 1},
    }


# --- Fase 2: importar ---------------------------------------------------------
def importar(session: Session, *, grupo_id: uuid.UUID, clientes: list[dict]) -> dict:
    """Crea y actualiza lo que la pantalla confirmó. **Revalida todo.**"""
    if not clientes:
        raise ReglaNegocio("no hay clientes que importar")

    creados, actualizados, omitidos = [], [], []
    for entrada in clientes:
        nombre = (entrada.get("nombre") or "").strip()
        if entrada.get("accion") == "omitir":
            omitidos.append({"nombre": nombre, "motivo": "omitido en la revisión"})
            continue
        try:
            # Savepoint por fila: un cliente que no entra no puede llevarse
            # puestos a los cien que ya entraron.
            with session.begin_nested():
                existente = _existente(session, grupo_id, entrada)
                if existente is None:
                    cliente = _crear_uno(session, grupo_id, entrada, nombre)
                else:
                    cliente = _actualizar_uno(session, existente, entrada, nombre)
        except AppError as e:
            omitidos.append({"nombre": nombre, "motivo": str(e)})
            continue
        destino = actualizados if existente is not None else creados
        destino.append({"id": str(cliente.id), "nombre": nombre})
    return {"creadas": creados, "actualizadas": actualizados, "omitidas": omitidos}


def _existente(session: Session, grupo_id: uuid.UUID, entrada: dict) -> Cliente | None:
    """Por `id` si vino, si no por documento. Un id que no resuelve es una
    fila omitida con motivo, nunca un 404 que tumbe la importación entera."""
    if entrada.get("id"):
        try:
            cliente_id = uuid.UUID(str(entrada["id"]))
        except (ValueError, AttributeError, TypeError):
            raise ReglaNegocio("el ID no es un identificador válido") from None
        cliente = session.get(Cliente, cliente_id)
        if (
            cliente is None
            or cliente.grupo_id != grupo_id
            or cliente.deleted_at is not None
        ):
            raise ReglaNegocio("el ID no corresponde a ningún cliente del grupo")
        return cliente
    documento = (entrada.get("documento") or "").strip()
    if not documento:
        return None
    juridico = session.scalar(
        select(Cliente).where(
            Cliente.grupo_id == grupo_id,
            Cliente.ruc == documento,
            Cliente.deleted_at.is_(None),
        )
    )
    if juridico is not None:
        return juridico
    return session.scalar(
        select(Cliente)
        .join(Persona, Persona.id == Cliente.persona_id)
        .where(
            Cliente.grupo_id == grupo_id,
            Cliente.deleted_at.is_(None),
            Persona.numero_documento == documento,
        )
    )


def _crear_uno(session: Session, grupo_id, entrada: dict, nombre: str) -> Cliente:
    return clientes_uc.crear_cliente(
        session,
        grupo_id=grupo_id,
        nombre=nombre,
        telefono=entrada.get("telefono") or None,
        numero_documento=entrada.get("documento") or None,
        email=entrada.get("email") or None,
        direccion=entrada.get("contacto") or None,
        fecha_nacimiento=planilla.a_fecha(entrada.get("fecha_nacimiento")),
        tipo_documento=_tipo_documento(entrada),
        # La planilla manda sobre el nombre: una consulta externa por fila
        # es lo que hace inviable una carga de trescientas (ADR-051).
        consultar_documento=False,
    )


def _actualizar_uno(
    session: Session, cliente: Cliente, entrada: dict, nombre: str
) -> Cliente:
    documento = (entrada.get("documento") or "").strip()
    if cliente.tipo == "juridico":
        return clientes_uc.editar_cliente(
            session,
            cliente.id,
            consultar_documento=False,
            razon_social=nombre or None,
            ruc=documento or None,
            contacto=entrada.get("contacto") or None,
        )
    # Natural: lo único que este módulo puede escribir es el documento. El
    # resto vive en `persona` y la revisión ya lo reportó.
    if not documento:
        raise ReglaNegocio(
            "de un cliente natural que ya existe solo se completa el documento; "
            "el resto se corrige en Personas"
        )
    return clientes_uc.actualizar_documento(
        session,
        cliente_id=cliente.id,
        numero_documento=documento,
        tipo_documento=_tipo_documento(entrada),
    )


def _tipo_documento(entrada: dict) -> str:
    tipo = (entrada.get("tipo_documento") or "").strip().lower()
    return tipo if tipo in clientes_uc.TIPOS_DOCUMENTO_NATURAL else "dni"


# --- Lectura del archivo ------------------------------------------------------
def _leer(libro) -> list[dict]:
    columnas = planilla.cabecera(
        libro, HOJA_CLIENTES, requeridas=("Nombre / Razón social",)
    )
    leidas = []
    for numero, fila in planilla.filas(libro, HOJA_CLIENTES):
        nombre = planilla.celda(fila, columnas, "Nombre / Razón social")
        if not nombre:
            continue
        leidas.append(
            {
                "fila": numero,
                "id": planilla.a_uuid(planilla.celda(fila, columnas, "ID")),
                "nombre": nombre,
                "tipo_documento": planilla.celda(
                    fila, columnas, "Tipo de documento"
                ).lower(),
                "documento": planilla.celda(fila, columnas, "Número de documento"),
                "telefono": planilla.celda(fila, columnas, "Teléfono"),
                "email": planilla.celda(fila, columnas, "Email"),
                "contacto": planilla.celda(fila, columnas, "Dirección / contacto"),
                "nacimiento": planilla.celda(fila, columnas, "Fecha de nacimiento"),
            }
        )
    return leidas
