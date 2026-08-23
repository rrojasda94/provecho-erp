"""El recetario se baja, se edita en Excel y se vuelve a subir (RN-COM-031).

Un recetario de restaurante no se teclea receta por receta: llega en una
hoja de cálculo que ya existe, con decenas de platos y cientos de líneas. Y
corregir el rendimiento de treinta recetas ya cargadas tampoco se hace
abriendo treinta fichas: por eso `exportar` devuelve la misma plantilla con
los datos adentro (ADR-052).

**Dos fases, sin tabla de staging.** `validar` parsea y devuelve qué está
bien y qué no, **sin guardar nada**; la pantalla resuelve los insumos que no
reconoció —eligiendo uno existente, creándolo, u omitiendo esas filas— y
recién entonces `importar` commitea. La alternativa era una tabla temporal
con su propio ciclo de vida y su propia limpieza; con dos llamadas sin
estado, una importación abandonada no deja nada que barrer.

**La columna `ID` decide alta o actualización**: vacía es alta, llena es la
receta que el export nombró. El nombre no sirve de clave porque el nombre es
justamente lo que alguien puede querer cambiar (ADR-052).

**Qué se borra lo decide una persona, receta por receta.** Al actualizar, los
ingredientes que el archivo no menciona se conservan salvo que la revisión
diga `quitar` para esa receta. Subir una hoja parcial por error no puede
vaciar una receta sin que alguien vea cuántas líneas pierde.

**El servidor revalida todo en la segunda fase.** Lo que vuelve de la
pantalla es un JSON que el cliente pudo editar: confiar en que sigue siendo
el archivo que se validó sería dejar que un POST cree recetas con insumos de
otra empresa.

Se reusa `crear_receta`/`editar_receta`/`agregar_item` en vez de insertar
directo: son las que saben del nombre único por empresa, de la unidad, de la
merma y de la aritmética tecleada (RN-COM-024). Un importador con su propia
lógica sería un segundo juego de reglas que se separa del primero.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.application import recetas as recetas_uc
from src.modules.inventory.application.errors import AppError, ReglaNegocio
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Receta,
    RecetaItem,
    UnidadMedida,
)
from src.shared import planilla
from src.shared.texto import a_titulo

HOJA_RECETAS = "Recetas"
HOJA_INGREDIENTES = "Ingredientes"
HOJA_INSTRUCCIONES = "Instrucciones"

CABECERA_RECETAS = ("ID", "Receta", "Rendimiento", "Unidad", "Produce el artículo")
CABECERA_INGREDIENTES = ("Receta", "Insumo", "Cantidad", "Merma %")

LARGO_NOMBRE = 150
"""Igual que `receta.nombre`. Se valida acá porque SQLite no aplica el largo
de un VARCHAR y el test pasaría en verde para reventar contra Postgres."""


# --- Plantilla y export -------------------------------------------------------
def plantilla() -> bytes:
    """El archivo que se ofrece cuando todavía no hay nada que exportar.

    Va con una fila de ejemplo en cada hoja: una plantilla vacía obliga a
    adivinar si "Cantidad" son gramos o kilos, y el ejemplo lo contesta sin
    que nadie tenga que leer las instrucciones. La columna `ID` va vacía —
    una fila sin id es un alta.
    """
    return _libro(
        [
            ["", "Salsa De Tomate", 1, "Litro", "Salsa De Tomate"],
            ["", "Pizza Personal", 1, "Unidad", ""],
        ],
        [
            ["Salsa De Tomate", "Tomate", 1200, 5],
            ["Pizza Personal", "Masa Cruda", 1, 0],
            ["Pizza Personal", "Queso Mozzarella", "450/3", 3],
        ],
    )


def exportar(session: Session, *, empresa_id: uuid.UUID) -> bytes:
    """El recetario de la empresa en el formato que `validar` sabe leer.

    Es la plantilla con los datos adentro: lo que baja se edita y se vuelve a
    subir sin traducir nada (ADR-052).
    """
    udms = {u.id: u.nombre for u in session.scalars(select(UnidadMedida))}
    articulos = {
        a.id: a.nombre
        for a in session.scalars(select(Articulo).where(Articulo.empresa_id == empresa_id))
    }
    recetas = list(
        session.scalars(
            select(Receta).where(Receta.empresa_id == empresa_id).order_by(Receta.nombre)
        )
    )
    items: dict[uuid.UUID, list[RecetaItem]] = {}
    if recetas:
        consulta = select(RecetaItem).where(
            RecetaItem.receta_id.in_([r.id for r in recetas])
        )
        for item in session.scalars(consulta):
            items.setdefault(item.receta_id, []).append(item)

    filas_recetas = [
        [
            str(r.id),
            r.nombre,
            _numero(r.rendimiento_cantidad),
            udms.get(r.rendimiento_unidad_medida_id, ""),
            articulos.get(r.articulo_id, "") if r.articulo_id else "",
        ]
        for r in recetas
    ]
    filas_ingredientes = [
        [
            r.nombre,
            articulos.get(i.articulo_id, ""),
            # La expresión tecleada manda sobre el resultado: exportar `150`
            # donde alguien escribió `450/3` pierde justo lo que RN-COM-024
            # existe para conservar.
            i.expresion or _numero(i.cantidad),
            _numero(i.merma_pct),
        ]
        for r in recetas
        for i in items.get(r.id, [])
    ]
    return _libro(filas_recetas, filas_ingredientes)


def _libro(recetas: list[list], ingredientes: list[list]) -> bytes:
    return planilla.escribir(
        {
            HOJA_RECETAS: [list(CABECERA_RECETAS), *recetas],
            HOJA_INGREDIENTES: [list(CABECERA_INGREDIENTES), *ingredientes],
            HOJA_INSTRUCCIONES: [[linea] for linea in _INSTRUCCIONES],
        }
    )


_INSTRUCCIONES = (
    "Cómo llenar esta plantilla",
    "",
    "Hoja «Recetas»: una fila por receta.",
    "  · ID: no se toca. Si viene lleno, esa fila ACTUALIZA la receta que",
    "    nombra; si va vacío, se crea una receta nueva.",
    "  · Receta: el nombre. Con ID vacío, un nombre que ya existe se omite.",
    "  · Rendimiento: cuánto produce una preparación. Debe ser mayor que cero.",
    "  · Unidad: el nombre exacto de la unidad de medida (Unidad, Gramo, Litro…).",
    "  · Produce el artículo: solo para SUBRECETAS — el insumo que la receta",
    "    genera y que después se usa en otra. Vacío = es un producto de venta.",
    "",
    "Hoja «Ingredientes»: una fila por insumo de cada receta.",
    "  · Receta: tiene que coincidir exactamente con la hoja «Recetas».",
    "  · Insumo: el nombre del artículo. Si no existe, la pantalla te deja",
    "    elegir uno, crearlo, u omitir esa fila — no se pierde el trabajo.",
    "  · Cantidad: acepta aritmética tecleada («450/3», «2*1.5»).",
    "  · Merma %: cuánto se pierde al prepararlo. 0 si no se pierde nada.",
    "",
    "Al actualizar una receta, los ingredientes que el archivo NO menciona se",
    "conservan. La pantalla te deja pedir que se quiten, receta por receta, y",
    "te dice cuántas líneas perderías antes de confirmar.",
    "",
    "Nada se guarda hasta que revises el resultado y confirmes.",
)


# --- Fase 1: validar ----------------------------------------------------------
def validar(session: Session, *, empresa_id: uuid.UUID, contenido: bytes) -> dict:
    """Parsea el archivo y dice qué entra, qué actualiza y qué no. **No guarda.**"""
    libro = planilla.abrir(contenido, requeridas=(HOJA_RECETAS, HOJA_INGREDIENTES))
    cabeceras = _leer_recetas(libro)
    ingredientes = _leer_ingredientes(libro)

    udms = {u.nombre.lower(): u for u in session.scalars(select(UnidadMedida))}
    articulos = {
        a.nombre.lower(): a
        for a in session.scalars(
            select(Articulo).where(Articulo.empresa_id == empresa_id)
        )
    }
    de_la_empresa = list(
        session.scalars(select(Receta).where(Receta.empresa_id == empresa_id))
    )
    por_id = {r.id: r for r in de_la_empresa}
    por_nombre = {r.nombre.lower(): r for r in de_la_empresa}
    # Copiar-pegar una fila entera es el accidente esperable: dos filas con el
    # mismo ID escribirían dos veces sobre el mismo registro.
    repetidos = {
        f["id"] for f in cabeceras if f["id"] and _cuantas(cabeceras, f["id"]) > 1
    }

    recetas = [
        _revisar_receta(
            session,
            fila,
            [i for i in ingredientes if i["receta"].lower() == fila["nombre"].lower()],
            udms,
            articulos,
            por_id,
            por_nombre,
            repetidos,
        )
        for fila in cabeceras
    ]

    return {
        "recetas": recetas,
        # Los nombres que el archivo trae y el catálogo no conoce. La
        # pantalla los resuelve uno por uno antes de dejar importar.
        "insumos_desconocidos": sorted(
            {
                i["insumo"]
                for r in recetas
                for i in r["ingredientes"]
                if i["articulo_id"] is None
            }
        ),
        "ingredientes_sin_receta": _huerfanas(cabeceras, ingredientes),
        "listas": sum(
            1 for r in recetas if not r["problemas"] and r["accion"] == "crear"
        ),
        "a_actualizar": sum(
            1 for r in recetas if not r["problemas"] and r["accion"] == "actualizar"
        ),
        "con_problema": sum(1 for r in recetas if r["problemas"]),
    }


def _revisar_receta(
    session, fila, propias, udms, articulos, por_id, por_nombre, repetidos
) -> dict:
    problemas = []
    existente = None
    accion = "crear"
    if fila["id"]:
        # Una fila con ID pide actualizar, resuelva o no: degradarla a alta
        # convertiría un ID mal pegado en una receta duplicada, en silencio.
        accion = "actualizar"
        if fila["id"] in repetidos:
            problemas.append("el mismo ID aparece en más de una fila")
        existente = por_id.get(fila["id"])
        if existente is None:
            problemas.append("el ID no corresponde a ninguna receta de la empresa")

    nombre = a_titulo(fila["nombre"]) or fila["nombre"]
    if not planilla.largo_ok(nombre, LARGO_NOMBRE):
        problemas.append(f"el nombre supera los {LARGO_NOMBRE} caracteres")
    choque = por_nombre.get(nombre.lower())
    if choque is not None and (existente is None or choque.id != existente.id):
        problemas.append("ya existe una receta con ese nombre")

    udm = udms.get((fila["unidad"] or "").lower())
    if udm is None:
        problemas.append(f"unidad desconocida: «{fila['unidad']}»")
    cantidad = planilla.a_decimal(fila["rendimiento"])
    if cantidad is None or cantidad <= 0:
        problemas.append(f"rendimiento inválido: «{fila['rendimiento']}»")
    produce = fila["produce"]
    articulo_producido = articulos.get((produce or "").lower())
    if produce and articulo_producido is None:
        problemas.append(f"el artículo que produce no existe: «{produce}»")
    if not propias and accion == "crear":
        problemas.append("la receta no tiene ingredientes")

    lineas = [_revisar_ingrediente(i, articulos) for i in propias]
    ausentes = _ausentes(session, existente, lineas) if existente else []

    return {
        "fila": fila["fila"],
        # El ID que trajo el archivo, resuelva o no: la fase 2 lo vuelve a
        # buscar y lo omite con motivo si no es de esta empresa.
        "id": str(fila["id"]) if fila["id"] else None,
        "accion": accion,
        # Lo que el archivo no menciona se conserva salvo que la pantalla pida
        # lo contrario para esta receta (ADR-052).
        "ingredientes_ausentes": "conservar",
        "nombre": nombre,
        "rendimiento": str(fila["rendimiento"]),
        "unidad": fila["unidad"],
        "unidad_medida_id": str(udm.id) if udm else None,
        "produce": produce,
        "articulo_producido_id": (
            str(articulo_producido.id) if articulo_producido else None
        ),
        "ingredientes": lineas,
        # Solo para pintar: la fase 2 vuelve a calcular todo desde la base.
        "cambios": _cambios(existente, nombre, cantidad, udm) if existente else [],
        "se_quitarian": ausentes,
        "problemas": problemas,
    }


def _revisar_ingrediente(linea, articulos) -> dict:
    articulo = articulos.get(linea["insumo"].lower())
    problemas = []
    if articulo is None:
        problemas.append("no existe en el catálogo")
    if planilla.a_decimal(linea["merma"]) is None:
        problemas.append(f"merma inválida: «{linea['merma']}»")
    if not planilla.largo_ok(linea["cantidad"], recetas_uc.LARGO_EXPRESION):
        problemas.append(
            f"la cantidad supera los {recetas_uc.LARGO_EXPRESION} caracteres"
        )
    return {
        "fila": linea["fila"],
        "insumo": linea["insumo"],
        # `None` = la pantalla tiene que resolverlo. La cantidad NO se
        # evalúa acá: puede ser aritmética tecleada («450/3») y quien sabe
        # redondearla es `agregar_item`, con los decimales de la unidad del
        # insumo — que justamente todavía no se conoce (RN-COM-024).
        "articulo_id": str(articulo.id) if articulo else None,
        "cantidad": str(linea["cantidad"]),
        "merma_pct": str(linea["merma"]),
        "problemas": problemas,
    }


def _cambios(receta: Receta, nombre: str, cantidad, udm) -> list[str]:
    cambios = []
    if nombre and nombre != receta.nombre:
        cambios.append(f"nombre: {receta.nombre} → {nombre}")
    if cantidad is not None and cantidad != receta.rendimiento_cantidad:
        cambios.append(
            f"rendimiento: {_numero(receta.rendimiento_cantidad)} → {_numero(cantidad)}"
        )
    if udm is not None and udm.id != receta.rendimiento_unidad_medida_id:
        cambios.append(f"unidad: → {udm.nombre}")
    return cambios


def _ausentes(session: Session, receta: Receta, lineas: list[dict]) -> list[str]:
    """Ingredientes que la receta tiene y el archivo no menciona."""
    nombrados = {i["articulo_id"] for i in lineas if i["articulo_id"]}
    fuera = [
        i for i in _items(session, receta.id) if str(i.articulo_id) not in nombrados
    ]
    if not fuera:
        return []
    consulta = select(Articulo).where(Articulo.id.in_([i.articulo_id for i in fuera]))
    nombres = {a.id: a.nombre for a in session.scalars(consulta)}
    return sorted(nombres.get(i.articulo_id, str(i.articulo_id)) for i in fuera)


def _huerfanas(cabeceras, ingredientes) -> list[str]:
    """Ingredientes que nombran una receta que la otra hoja no declara.

    Es el error de tipeo más común del formato —"Pizza Personal" en una hoja
    y "Pizza personal" en la otra— y callarlo importaría la receta sin sus
    insumos.
    """
    declaradas = {c["nombre"].lower() for c in cabeceras}
    return sorted(
        {i["receta"] for i in ingredientes if i["receta"].lower() not in declaradas}
    )


# --- Fase 2: importar ---------------------------------------------------------
def importar(session: Session, *, empresa_id: uuid.UUID, recetas: list[dict]) -> dict:
    """Crea y actualiza lo que la pantalla confirmó. **Revalida todo**: lo que
    llega es un JSON que el cliente pudo editar."""
    if not recetas:
        raise ReglaNegocio("no hay recetas que importar")

    creadas, actualizadas, omitidas = [], [], []
    for entrada in recetas:
        nombre = (entrada.get("nombre") or "").strip()
        if entrada.get("accion") == "omitir":
            # Único caso en que se le hace caso al cliente sin verificar:
            # decir que no siempre es seguro.
            omitidas.append({"nombre": nombre, "motivo": "omitida en la revisión"})
            continue
        try:
            # Savepoint por receta, no `rollback()`: una receta que no entra
            # no puede llevarse puestas a las cincuenta que ya entraron. Y
            # tampoco puede quedar a medias —creada sin sus ingredientes—,
            # que es lo que pasaría sin transacción anidada.
            with session.begin_nested():
                existente = _existente(session, empresa_id, entrada)
                if existente is None:
                    receta = _crear_una(session, empresa_id, entrada, nombre)
                else:
                    receta = _actualizar_una(session, existente, entrada, nombre)
        except AppError as e:
            omitidas.append({"nombre": nombre, "motivo": str(e)})
            continue
        destino = actualizadas if existente is not None else creadas
        destino.append({"id": str(receta.id), "nombre": receta.nombre})
    return {"creadas": creadas, "actualizadas": actualizadas, "omitidas": omitidas}


def _existente(session: Session, empresa_id: uuid.UUID, entrada: dict) -> Receta | None:
    """La receta que el `id` nombra, **si es de esta empresa**.

    Un id que no resuelve es una fila omitida con motivo, nunca un 404 que
    tumbe la importación entera.
    """
    if not entrada.get("id"):
        return None
    try:
        receta_id = uuid.UUID(str(entrada["id"]))
    except (ValueError, AttributeError, TypeError):
        raise ReglaNegocio("el ID no es un identificador válido") from None
    receta = session.get(Receta, receta_id)
    if receta is None or receta.empresa_id != empresa_id:
        raise ReglaNegocio("el ID no corresponde a ninguna receta de la empresa")
    return receta


def _crear_una(session: Session, empresa_id, entrada: dict, nombre: str) -> Receta:
    receta = recetas_uc.crear_receta(
        session,
        empresa_id=empresa_id,
        nombre=nombre,
        rendimiento_cantidad=Decimal(str(entrada["rendimiento"])),
        rendimiento_unidad_medida_id=uuid.UUID(str(entrada["unidad_medida_id"])),
        # `crear_receta` valida que el artículo sea de la empresa: por eso el
        # id del cliente no puede colar una subreceta de otra.
        articulo_id=(
            uuid.UUID(str(entrada["articulo_producido_id"]))
            if entrada.get("articulo_producido_id")
            else None
        ),
    )
    for linea in entrada.get("ingredientes", []):
        if not linea.get("articulo_id"):
            continue  # omitido a propósito desde la pantalla
        recetas_uc.agregar_item(
            session,
            receta.id,
            articulo_id=uuid.UUID(str(linea["articulo_id"])),
            expresion=str(linea["cantidad"]),
            merma_pct=Decimal(str(linea.get("merma_pct") or 0)),
        )
    return receta


def _actualizar_una(
    session: Session, receta: Receta, entrada: dict, nombre: str
) -> Receta:
    recetas_uc.editar_receta(
        session,
        receta.id,
        nombre=nombre or None,
        rendimiento_cantidad=Decimal(str(entrada["rendimiento"])),
        rendimiento_unidad_medida_id=uuid.UUID(str(entrada["unidad_medida_id"])),
        articulo_id=(
            uuid.UUID(str(entrada["articulo_producido_id"]))
            if entrada.get("articulo_producido_id")
            else None
        ),
    )
    por_articulo = {i.articulo_id: i for i in _items(session, receta.id)}
    nombrados = set()
    for linea in entrada.get("ingredientes", []):
        if not linea.get("articulo_id"):
            continue  # omitido a propósito desde la pantalla
        articulo_id = uuid.UUID(str(linea["articulo_id"]))
        nombrados.add(articulo_id)
        merma = Decimal(str(linea.get("merma_pct") or 0))
        item = por_articulo.get(articulo_id)
        if item is None:
            recetas_uc.agregar_item(
                session,
                receta.id,
                articulo_id=articulo_id,
                expresion=str(linea["cantidad"]),
                merma_pct=merma,
            )
        else:
            recetas_uc.editar_item(
                session,
                item.id,
                expresion=str(linea["cantidad"]),
                merma_pct=merma,
            )
    if entrada.get("ingredientes_ausentes") == "quitar":
        for articulo_id, item in por_articulo.items():
            if articulo_id not in nombrados:
                recetas_uc.eliminar_item(session, item.id)
    return receta


def _items(session: Session, receta_id: uuid.UUID) -> list[RecetaItem]:
    return list(
        session.scalars(select(RecetaItem).where(RecetaItem.receta_id == receta_id))
    )


# --- Lectura del archivo ------------------------------------------------------
def _leer_recetas(libro) -> list[dict]:
    columnas = planilla.cabecera(
        libro, HOJA_RECETAS, requeridas=("Receta", "Rendimiento", "Unidad")
    )
    leidas = []
    for numero, fila in planilla.filas(libro, HOJA_RECETAS):
        nombre = planilla.celda(fila, columnas, "Receta")
        if not nombre:
            continue
        leidas.append(
            {
                "fila": numero,
                "id": planilla.a_uuid(planilla.celda(fila, columnas, "ID")),
                "nombre": nombre,
                "rendimiento": planilla.celda(fila, columnas, "Rendimiento"),
                "unidad": planilla.celda(fila, columnas, "Unidad"),
                "produce": planilla.celda(fila, columnas, "Produce el artículo") or None,
            }
        )
    return leidas


def _leer_ingredientes(libro) -> list[dict]:
    columnas = planilla.cabecera(
        libro, HOJA_INGREDIENTES, requeridas=("Receta", "Insumo", "Cantidad")
    )
    leidas = []
    for numero, fila in planilla.filas(libro, HOJA_INGREDIENTES):
        receta = planilla.celda(fila, columnas, "Receta")
        insumo = planilla.celda(fila, columnas, "Insumo")
        if not receta or not insumo:
            continue
        leidas.append(
            {
                "fila": numero,
                "receta": receta,
                "insumo": insumo,
                "cantidad": planilla.celda(fila, columnas, "Cantidad"),
                "merma": planilla.celda(fila, columnas, "Merma %") or "0",
            }
        )
    return leidas


def _cuantas(cabeceras: list[dict], id_: uuid.UUID) -> int:
    return sum(1 for c in cabeceras if c["id"] == id_)


def _numero(valor: Decimal) -> str:
    """Sin ceros de relleno: `1200.0000` se lee `1200`, no `1200.0000`."""
    return format(Decimal(valor).normalize(), "f")
