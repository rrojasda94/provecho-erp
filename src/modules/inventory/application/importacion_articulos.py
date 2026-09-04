"""El catálogo de artículos se baja, se edita en Excel y se vuelve a subir
(RN-INV-025, ADR-052).

Mismo recorrido que el recetario: `exportar` da la plantilla con los datos
adentro, `validar` dice qué entra y qué no **sin guardar nada**, y `importar`
revalida lo que la pantalla confirmó. La razón de existir es la misma —
teclear trescientos artículos de a uno es el trabajo que hace que el ERP no se
adopte— más una propia: hasta ahora, cuando el importador de recetas
encontraba un insumo que no existía, había que crearlo a mano.

**La identidad es `ID`, o el `Código` si el `ID` viene vacío.** El código
interno es corto, estable y ya se usa; el nombre no sirve de clave porque el
nombre es lo que se edita (ADR-052).

**La unidad de un artículo existente no se cambia.** `editar_articulo` la
excluye a propósito: el stock, los movimientos y las recetas ya cargadas están
expresados en la unidad actual, así que cambiarla reinterpreta en silencio todo
lo que ya existe. Una fila que la cambie **se reporta**, no se ignora.

Se reusan `crear_articulo` y `editar_articulo` en vez de insertar directo: son
las que saben del código único, del formato del nombre y de qué campos son
editables.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.inventory.application import catalogo as catalogo_uc
from src.modules.inventory.application.errors import AppError, ReglaNegocio
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    Sku,
    UnidadMedida,
)
from src.shared import planilla
from src.shared.texto import a_titulo

HOJA_ARTICULOS = "Artículos"
HOJA_SKUS = "SKUs"
HOJA_INSTRUCCIONES = "Instrucciones"

CABECERA_ARTICULOS = (
    "ID",
    "Código",
    "Nombre",
    "Tipo",
    "Unidad",
    "Categoría",
    "Costo promedio",
    "Controla lote",
    "Días alerta vencimiento",
    "Archivado",
)
CABECERA_SKUS = ("Artículo", "Código", "Código de barras", "Activo")

LARGO_CODIGO = 4
"""Igual que `articulo.id_interno`, y **único en todo el grupo**, no por
empresa. Se valida acá porque SQLite no aplica el largo de un VARCHAR: la fila
pasaría en verde para reventar contra Postgres."""

LARGO_NOMBRE = 150
LARGO_CODIGO_SKU = 50


# --- Plantilla y export -------------------------------------------------------
def plantilla() -> bytes:
    """El archivo que se ofrece cuando todavía no hay catálogo que exportar."""
    return _libro(
        [
            ["", "TOMA", "Tomate", "insumo", "Gramo", "Abarrotes", 0.01, "No", "", "No"],
            ["", "LECH", "Leche", "insumo", "Litro", "Lácteos", 4.5, "Sí", 3, "No"],
        ],
        [["TOMA", "TOMA-CAJA", "7501234567890", "Sí"]],
    )


def exportar(session: Session, *, empresa_id: uuid.UUID) -> bytes:
    """El catálogo de la empresa en el formato que `validar` sabe leer."""
    udms = {u.id: u.nombre for u in session.scalars(select(UnidadMedida))}
    categorias = {
        c.id: c.nombre
        for c in session.scalars(
            select(Categoria).where(Categoria.empresa_id == empresa_id)
        )
    }
    articulos = list(
        session.scalars(
            select(Articulo)
            .where(Articulo.empresa_id == empresa_id)
            .order_by(Articulo.id_interno)
        )
    )
    skus: dict[uuid.UUID, list[Sku]] = {}
    if articulos:
        consulta = select(Sku).where(Sku.articulo_id.in_([a.id for a in articulos]))
        for sku in session.scalars(consulta):
            skus.setdefault(sku.articulo_id, []).append(sku)

    return _libro(
        [
            [
                str(a.id),
                a.id_interno,
                a.nombre,
                a.tipo,
                udms.get(a.unidad_medida_id, ""),
                categorias.get(a.categoria_id, "") if a.categoria_id else "",
                _numero(a.costo_promedio),
                _si_no(a.controla_lote),
                a.dias_alerta_vencimiento if a.dias_alerta_vencimiento else "",
                _si_no(a.archivado),
            ]
            for a in articulos
        ],
        [
            [a.id_interno, s.codigo, s.codigo_barras or "", _si_no(s.activo)]
            for a in articulos
            for s in skus.get(a.id, [])
        ],
    )


def _libro(articulos: list[list], skus: list[list]) -> bytes:
    return planilla.escribir(
        {
            HOJA_ARTICULOS: [list(CABECERA_ARTICULOS), *articulos],
            HOJA_SKUS: [list(CABECERA_SKUS), *skus],
            HOJA_INSTRUCCIONES: [[linea] for linea in _INSTRUCCIONES],
        }
    )


_INSTRUCCIONES = (
    "Cómo llenar esta plantilla",
    "",
    "Hoja «Artículos»: una fila por artículo.",
    "  · ID: no se toca. Si viene lleno, esa fila ACTUALIZA ese artículo.",
    "  · Código: 4 caracteres, único en todo el grupo. Es obligatorio y sirve",
    "    de identidad cuando el ID va vacío — por eso un código que ya existe",
    "    actualiza en vez de crear.",
    "  · Nombre, Tipo (insumo, subreceta, mercaderia, empaque…).",
    "  · Unidad: el nombre exacto de la unidad de medida. En un artículo que",
    "    YA EXISTE no se puede cambiar: el stock y las recetas ya cargadas",
    "    están expresados en la unidad actual. Si la cambias, la fila se",
    "    reporta y no entra.",
    "  · Categoría: opcional. Si no existe, la pantalla te deja elegir otra,",
    "    crearla, o dejar el artículo sin categoría.",
    "  · Controla lote / Archivado: Sí o No.",
    "  · Días alerta vencimiento: en blanco = sin ventana propia.",
    "",
    "Hoja «SKUs»: una fila por presentación.",
    "  · Artículo: el CÓDIGO del artículo, no su nombre.",
    "  · Código: único. Un SKU que ya existe se informa y no se toca —",
    "    todavía no se editan por planilla.",
    "",
    "Una celda vacía significa «no tocar», no «vaciar».",
    "Nada se guarda hasta que revises el resultado y confirmes.",
)


# --- Fase 1: validar ----------------------------------------------------------
def validar(session: Session, *, empresa_id: uuid.UUID, contenido: bytes) -> dict:
    """Parsea el archivo y dice qué entra, qué actualiza y qué no."""
    libro = planilla.abrir(contenido, requeridas=(HOJA_ARTICULOS,))
    filas = _leer_articulos(libro)
    filas_sku = _leer_skus(libro) if HOJA_SKUS in libro.sheetnames else []

    udms = {u.nombre.lower(): u for u in session.scalars(select(UnidadMedida))}
    categorias = {
        c.nombre.lower(): c
        for c in session.scalars(
            select(Categoria).where(Categoria.empresa_id == empresa_id)
        )
    }
    de_la_empresa = list(
        session.scalars(select(Articulo).where(Articulo.empresa_id == empresa_id))
    )
    por_id = {a.id: a for a in de_la_empresa}
    por_codigo = {a.id_interno.lower(): a for a in de_la_empresa}
    codigos_sku = {
        s.codigo.lower() for s in session.scalars(select(Sku))
    }
    repetidos = _repetidos(filas)

    articulos = [
        _revisar(
            fila,
            [s for s in filas_sku if s["articulo"].lower() == fila["codigo"].lower()],
            udms,
            categorias,
            por_id,
            por_codigo,
            codigos_sku,
            repetidos,
        )
        for fila in filas
    ]

    declarados = {f["codigo"].lower() for f in filas}
    return {
        "articulos": articulos,
        # Las referencias que el archivo trae y el catálogo no conoce. Nunca se
        # autocrean: un "Bevidas" mal tecleado dejaría una categoría duplicada
        # que después hay que fusionar a mano (ADR-046).
        "unidades_desconocidas": sorted(
            {a["unidad"] for a in articulos if a["unidad"] and not a["unidad_medida_id"]}
        ),
        "categorias_desconocidas": sorted(
            {
                a["categoria"]
                for a in articulos
                if a["categoria"] and not a["categoria_id"]
            }
        ),
        "skus_sin_articulo": sorted(
            {s["articulo"] for s in filas_sku if s["articulo"].lower() not in declarados}
        ),
        "listas": sum(
            1 for a in articulos if not a["problemas"] and a["accion"] == "crear"
        ),
        "a_actualizar": sum(
            1 for a in articulos if not a["problemas"] and a["accion"] == "actualizar"
        ),
        "con_problema": sum(1 for a in articulos if a["problemas"]),
    }


def _revisar(
    fila, skus, udms, categorias, por_id, por_codigo, codigos_sku, repetidos
) -> dict:
    codigo = fila["codigo"].upper()
    accion, existente, problemas = _identidad(
        fila, codigo, por_id, por_codigo, repetidos
    )

    nombre = a_titulo(fila["nombre"]) or fila["nombre"]
    if not nombre:
        problemas.append("el nombre es obligatorio")
    elif not planilla.largo_ok(nombre, LARGO_NOMBRE):
        problemas.append(f"el nombre supera los {LARGO_NOMBRE} caracteres")

    udm = udms.get(fila["unidad"].lower())
    problemas += _problemas_de_unidad(fila["unidad"], udm, existente)

    categoria = categorias.get(fila["categoria"].lower()) if fila["categoria"] else None
    costo = planilla.a_decimal(fila["costo"]) if fila["costo"] else Decimal(0)
    if costo is None or costo < 0:
        problemas.append(f"costo inválido: «{fila['costo']}»")
    dias = planilla.a_decimal(fila["dias"]) if fila["dias"] else None
    if fila["dias"] and dias is None:
        problemas.append(f"días de alerta inválidos: «{fila['dias']}»")

    return {
        "fila": fila["fila"],
        "id": str(fila["id"]) if fila["id"] else (str(existente.id) if existente else None),
        "accion": accion,
        "codigo": codigo,
        "nombre": nombre,
        "tipo": fila["tipo"] or "insumo",
        "unidad": fila["unidad"],
        "unidad_medida_id": str(udm.id) if udm else None,
        "categoria": fila["categoria"],
        # `None` con `categoria` lleno = la pantalla tiene que resolverlo.
        "categoria_id": str(categoria.id) if categoria else None,
        "costo_promedio": str(costo if costo is not None else 0),
        "controla_lote": bool(planilla.a_booleano(fila["controla_lote"])),
        "dias_alerta_vencimiento": int(dias) if dias is not None else None,
        "archivado": bool(planilla.a_booleano(fila["archivado"])),
        "skus": [_revisar_sku(s, codigos_sku) for s in skus],
        "cambios": _cambios(existente, nombre, fila["tipo"], costo) if existente else [],
        "problemas": problemas,
    }


def _identidad(
    fila, codigo, por_id, por_codigo, repetidos
) -> tuple[str, Articulo | None, list[str]]:
    """Quién es esta fila: `ID` si vino, si no el `Código` (ADR-052)."""
    problemas: list[str] = []
    existente = None
    accion = "crear"

    if fila["id"]:
        # Una fila con ID pide actualizar, resuelva o no: degradarla a alta
        # convertiría un ID mal pegado en un artículo duplicado, en silencio.
        accion = "actualizar"
        if fila["id"] in repetidos["ids"]:
            problemas.append("el mismo ID aparece en más de una fila")
        existente = por_id.get(fila["id"])
        if existente is None:
            problemas.append("el ID no corresponde a ningún artículo de la empresa")

    if not codigo:
        problemas.append("el código es obligatorio")
    elif not planilla.largo_ok(codigo, LARGO_CODIGO):
        problemas.append(f"el código «{codigo}» supera los {LARGO_CODIGO} caracteres")
    if codigo.lower() in repetidos["codigos"]:
        problemas.append("el mismo código aparece en más de una fila")

    otro = por_codigo.get(codigo.lower())
    if not fila["id"]:
        if otro is not None:
            existente, accion = otro, "actualizar"
    elif existente is not None and otro is not None and otro.id != existente.id:
        problemas.append(f"el código «{codigo}» ya lo usa otro artículo")
    return accion, existente, problemas


def _problemas_de_unidad(unidad: str, udm, existente) -> list[str]:
    if existente is None:
        if not unidad:
            return ["la unidad es obligatoria"]
        if udm is None:
            return [f"unidad desconocida: «{unidad}»"]
        return []
    if udm is not None and udm.id != existente.unidad_medida_id:
        # Ignorarlo en silencio es el modo de falla que ADR-046 existe para
        # evitar: la persona creería que la cambió.
        return [
            "la unidad de un artículo que ya existe no se cambia por planilla: "
            "archívalo y crea uno nuevo"
        ]
    return []


def _revisar_sku(fila, codigos_sku) -> dict:
    problemas = []
    codigo = fila["codigo"]
    if not planilla.largo_ok(codigo, LARGO_CODIGO_SKU):
        problemas.append(f"el código supera los {LARGO_CODIGO_SKU} caracteres")
    if codigo.lower() in codigos_sku:
        # Todavía no hay `editar_sku`: informarlo es mejor que tocarlo a medias.
        problemas.append("ya existe: no se toca")
    return {
        "fila": fila["fila"],
        "codigo": codigo,
        "codigo_barras": fila["codigo_barras"] or None,
        "problemas": problemas,
    }


def _cambios(articulo: Articulo, nombre: str, tipo: str, costo) -> list[str]:
    cambios = []
    if nombre and nombre != articulo.nombre:
        cambios.append(f"nombre: {articulo.nombre} → {nombre}")
    if tipo and tipo != articulo.tipo:
        cambios.append(f"tipo: {articulo.tipo} → {tipo}")
    if costo is not None and costo != articulo.costo_promedio:
        cambios.append(
            f"costo: {_numero(articulo.costo_promedio)} → {_numero(costo)}"
        )
    return cambios


def _repetidos(filas: list[dict]) -> dict[str, set]:
    """Copiar-pegar una fila entera escribiría dos veces sobre el mismo
    registro. Se marcan las dos, no la segunda."""
    ids, codigos = [f["id"] for f in filas if f["id"]], [
        f["codigo"].lower() for f in filas if f["codigo"]
    ]
    return {
        "ids": {i for i in ids if ids.count(i) > 1},
        "codigos": {c for c in codigos if codigos.count(c) > 1},
    }


# --- Fase 2: importar ---------------------------------------------------------
def importar(session: Session, *, empresa_id: uuid.UUID, articulos: list[dict]) -> dict:
    """Crea y actualiza lo que la pantalla confirmó. **Revalida todo.**"""
    if not articulos:
        raise ReglaNegocio("no hay artículos que importar")

    creados, actualizados, omitidos = [], [], []
    for entrada in articulos:
        codigo = (entrada.get("codigo") or "").strip().upper()
        if entrada.get("accion") == "omitir":
            omitidos.append({"nombre": codigo, "motivo": "omitido en la revisión"})
            continue
        try:
            # Savepoint por fila: un artículo que no entra no puede llevarse
            # puestos a los cien que ya entraron, ni quedar sin sus SKUs.
            with session.begin_nested():
                existente = _existente(session, empresa_id, entrada, codigo)
                if existente is None:
                    articulo = _crear_uno(session, empresa_id, entrada, codigo)
                else:
                    articulo = _actualizar_uno(session, existente, entrada, codigo)
                _crear_skus(session, articulo, entrada.get("skus", []))
                # Después de los declarados, no antes: si la planilla trae los
                # suyos, esos mandan. La hoja «SKUs» es opcional y sin esto una
                # planilla que no la trae deja el artículo sin ninguno —
                # inerte para stock, conteo y recepción (RN-PRD-006). Así
                # entraron los 244 artículos de staging.
                catalogo_uc.asegurar_sku(session, articulo)
        except AppError as e:
            omitidos.append({"nombre": codigo, "motivo": str(e)})
            continue
        destino = actualizados if existente is not None else creados
        destino.append({"id": str(articulo.id), "nombre": articulo.nombre})
    return {"creadas": creados, "actualizadas": actualizados, "omitidas": omitidos}


def _existente(
    session: Session, empresa_id: uuid.UUID, entrada: dict, codigo: str
) -> Articulo | None:
    """Por `id` si vino, si no por código. Un id que no resuelve es una fila
    omitida con motivo, nunca un 404 que tumbe la importación entera."""
    if entrada.get("id"):
        try:
            articulo_id = uuid.UUID(str(entrada["id"]))
        except (ValueError, AttributeError, TypeError):
            raise ReglaNegocio("el ID no es un identificador válido") from None
        articulo = session.get(Articulo, articulo_id)
        if articulo is None or articulo.empresa_id != empresa_id:
            raise ReglaNegocio("el ID no corresponde a ningún artículo de la empresa")
        return articulo
    if entrada.get("accion") == "actualizar" and not codigo:
        raise ReglaNegocio("para actualizar hace falta el ID o el código")
    return session.scalar(
        select(Articulo).where(
            Articulo.empresa_id == empresa_id, Articulo.id_interno == codigo
        )
    )


def _crear_uno(session: Session, empresa_id, entrada: dict, codigo: str) -> Articulo:
    if not entrada.get("unidad_medida_id"):
        raise ReglaNegocio("falta la unidad de medida")
    return catalogo_uc.crear_articulo(
        session,
        empresa_id=empresa_id,
        id_interno=codigo,
        nombre=entrada["nombre"],
        unidad_medida_id=uuid.UUID(str(entrada["unidad_medida_id"])),
        tipo=entrada.get("tipo") or "insumo",
        categoria_id=_categoria(session, empresa_id, entrada),
        costo_promedio=Decimal(str(entrada.get("costo_promedio") or 0)),
        controla_lote=bool(entrada.get("controla_lote")),
        dias_alerta_vencimiento=entrada.get("dias_alerta_vencimiento"),
        # Los declara la planilla; `importar` cierra con `asegurar_sku` para
        # el que no traiga ninguno.
        sku_por_defecto=False,
    )


def _actualizar_uno(
    session: Session, articulo: Articulo, entrada: dict, codigo: str
) -> Articulo:
    if entrada.get("unidad_medida_id") and uuid.UUID(
        str(entrada["unidad_medida_id"])
    ) != articulo.unidad_medida_id:
        raise ReglaNegocio(
            "la unidad de un artículo que ya existe no se cambia por planilla"
        )
    return catalogo_uc.editar_articulo(
        session,
        articulo.id,
        id_interno=codigo or None,
        nombre=entrada.get("nombre") or None,
        tipo=entrada.get("tipo") or None,
        # Celda vacía = no tocar: un round-trip no puede borrar lo que el
        # export no supo representar.
        categoria_id=_categoria(session, articulo.empresa_id, entrada),
        costo_promedio=Decimal(str(entrada["costo_promedio"]))
        if entrada.get("costo_promedio") is not None
        else None,
        controla_lote=entrada.get("controla_lote"),
        dias_alerta_vencimiento=entrada.get("dias_alerta_vencimiento"),
        archivado=entrada.get("archivado"),
    )


def _categoria(session: Session, empresa_id, entrada: dict) -> uuid.UUID | None:
    if not entrada.get("categoria_id"):
        return None
    categoria_id = uuid.UUID(str(entrada["categoria_id"]))
    categoria = session.get(Categoria, categoria_id)
    if categoria is None or categoria.empresa_id != empresa_id:
        raise ReglaNegocio("la categoría no es de esta empresa")
    return categoria_id


def _crear_skus(session: Session, articulo: Articulo, skus: list[dict]) -> None:
    """Solo alta. No existe `editar_sku`, y tocar uno a medias sería peor que
    informarlo — la deuda está registrada."""
    for sku in skus:
        codigo = (sku.get("codigo") or "").strip()
        if not codigo:
            continue
        if session.scalar(select(Sku).where(Sku.codigo == codigo)) is not None:
            continue
        catalogo_uc.crear_sku(
            session,
            articulo_id=articulo.id,
            codigo=codigo,
            codigo_barras=sku.get("codigo_barras") or None,
        )


# --- Lectura del archivo ------------------------------------------------------
def _leer_articulos(libro) -> list[dict]:
    columnas = planilla.cabecera(
        libro, HOJA_ARTICULOS, requeridas=("Código", "Nombre")
    )
    leidas = []
    for numero, fila in planilla.filas(libro, HOJA_ARTICULOS):
        codigo = planilla.celda(fila, columnas, "Código")
        nombre = planilla.celda(fila, columnas, "Nombre")
        if not codigo and not nombre:
            continue
        leidas.append(
            {
                "fila": numero,
                "id": planilla.a_uuid(planilla.celda(fila, columnas, "ID")),
                "codigo": codigo,
                "nombre": nombre,
                "tipo": planilla.celda(fila, columnas, "Tipo"),
                "unidad": planilla.celda(fila, columnas, "Unidad"),
                "categoria": planilla.celda(fila, columnas, "Categoría"),
                "costo": planilla.celda(fila, columnas, "Costo promedio"),
                "controla_lote": planilla.celda(fila, columnas, "Controla lote"),
                "dias": planilla.celda(fila, columnas, "Días alerta vencimiento"),
                "archivado": planilla.celda(fila, columnas, "Archivado"),
            }
        )
    return leidas


def _leer_skus(libro) -> list[dict]:
    columnas = planilla.cabecera(libro, HOJA_SKUS, requeridas=("Artículo", "Código"))
    leidas = []
    for numero, fila in planilla.filas(libro, HOJA_SKUS):
        articulo = planilla.celda(fila, columnas, "Artículo")
        codigo = planilla.celda(fila, columnas, "Código")
        if not articulo or not codigo:
            continue
        leidas.append(
            {
                "fila": numero,
                "articulo": articulo,
                "codigo": codigo,
                "codigo_barras": planilla.celda(fila, columnas, "Código de barras"),
            }
        )
    return leidas


def _numero(valor: Decimal) -> str:
    return format(Decimal(valor).normalize(), "f")


def _si_no(valor: bool) -> str:
    return "Sí" if valor else "No"
