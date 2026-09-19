"""Compone las respuestas de la superficie pública del sitio de marca
(ADR-105). Solo llama a `application/queries_publicas.py` de otros
módulos — nunca a su dominio ni infraestructura (RN-WEB-001).
"""

import uuid

from src.config.settings import settings
from src.modules.inventory.application.queries_publicas import (
    articulos_publicos,
    insumos_de_recetas,
)
from src.modules.rrhh.application.queries_publicas import convocatorias_publicadas
from src.modules.sales.application.queries_publicas import (
    carta_publica,
    marca_publica,
    promociones_web_vigentes,
)
from src.modules.storefront.application import contenido as contenido_uc
from src.modules.storefront.application import fotos as fotos_uc
from src.modules.storefront.application.errors import NoEncontrado
from src.modules.storefront.domain.rules import abierto_ahora
from src.modules.users.application.queries_publicas import (
    empresas_de_marca,
    sucursales_publicas_de_marca,
)
from src.shared import fechas


class SitioNoConfigurado(NoEncontrado):
    """`STOREFRONT_MARCA_ID` está vacío o la marca no tiene sucursales
    activas: el sitio no está listo para servir. Nunca revela cuál de las
    dos cosas falta — el mensaje es igual de genérico que cualquier 404."""


def _marca_id() -> uuid.UUID:
    if not settings.storefront_marca_id:
        raise SitioNoConfigurado("sitio no configurado")
    return uuid.UUID(str(settings.storefront_marca_id))


def marca_actual_id() -> uuid.UUID:
    """La marca que sirve este sitio, para quien necesite resolverla fuera
    de una respuesta pública (ej. `application/pedidos.py` al confirmar un
    checkout). Mismo chequeo que `_marca_id()`, expuesto sin el guion bajo."""
    return _marca_id()


def _sucursal_id(session) -> uuid.UUID:
    if settings.storefront_sucursal_id:
        return uuid.UUID(str(settings.storefront_sucursal_id))
    sucursales = sucursales_publicas_de_marca(session, _marca_id())
    if not sucursales:
        raise SitioNoConfigurado("la marca no tiene sucursales activas")
    return sucursales[0]["id"]


def contenido(session) -> dict:
    marca_id = _marca_id()
    marca = marca_publica(session, marca_id)
    if marca is None:
        raise SitioNoConfigurado("sitio no configurado")
    return {
        "marca": marca,
        "contenido": contenido_uc.contenido_publico(session, marca_id),
    }


def _opciones(nodo: dict) -> dict:
    """Extras, sabores y pares excluidos de un nodo, con los campos que el
    cliente necesita para armar su línea (RN-WEB-001: enumerados, no el dict de
    `sales` tal cual)."""
    return {
        "extras": [
            {
                "id": e["producto_comercial_id"],
                "nombre": e["nombre"],
                "precio": e["precio_unitario"],
                "maximo": e["maximo"],
                "grupo_id": e["grupo_id"],
                "grupo_nombre": e["grupo_nombre"],
                "grupo_minimo": e["grupo_minimo"],
                "grupo_maximo": e["grupo_maximo"],
            }
            for e in nodo.get("extras", [])
        ],
        "atributos": [
            {
                "id": a["atributo_id"],
                "nombre": a["nombre"],
                "display": a["display"],
                "valores": [
                    {"id": v["id"], "nombre": v["nombre"], "precio_extra": v["precio_extra"]}
                    for v in a["valores"]
                ],
            }
            for a in nodo.get("atributos", [])
        ],
        "exclusiones": [list(par) for par in nodo.get("exclusiones", [])],
    }


def _ficha(
    nodo: dict,
    ingredientes_por_receta: dict[uuid.UUID, list[dict]],
    *,
    con_opciones: bool = False,
) -> dict:
    """Un producto o una variante, recortados a lo que RN-WEB-001 permite
    mostrar: nunca `id_interno`, `margen_contribucion` ni `empaque_id`. Las
    opciones (extras/sabores) solo van en el detalle de un producto: la carta
    completa las repetiría por cada tamaño de cada pizza."""
    ingredientes = ingredientes_por_receta.get(nodo.get("receta_id"), [])
    ficha = {
        "id": nodo["producto_comercial_id"],
        "nombre": nodo["nombre"],
        "descripcion": nodo.get("descripcion"),
        "precio": nodo["precio_unitario"],
        "disponible": not nodo.get("stock_bajo", False),
        "ingredientes": [
            {"id": ins["articulo_id"], "nombre": ins["nombre"]} for ins in ingredientes
        ],
    }
    if con_opciones:
        ficha.update(_opciones(nodo))
    return ficha


def carta(session, *, con_opciones: bool = False) -> dict:
    marca_id = _marca_id()
    sucursal_id = _sucursal_id(session)
    items = carta_publica(
        session,
        marca_id=marca_id,
        sucursal_id=sucursal_id,
        canal=settings.storefront_canal,
        modalidad=settings.storefront_modalidad,
    )
    receta_ids = {i["receta_id"] for i in items if i.get("receta_id")}
    for item in items:
        receta_ids.update(
            v["receta_id"] for v in item.get("variantes", []) if v.get("receta_id")
        )
    ingredientes_por_receta = insumos_de_recetas(session, list(receta_ids))

    categorias: dict[uuid.UUID, str] = {}
    productos = []
    for item in items:
        if item.get("categoria_id"):
            categorias.setdefault(item["categoria_id"], item.get("categoria_nombre") or "")
        variantes = [
            _ficha(v, ingredientes_por_receta, con_opciones=con_opciones)
            for v in item.get("variantes", [])
        ]
        precios_variantes = [v["precio"] for v in variantes]
        precio_desde = min(precios_variantes) if precios_variantes else item["precio_unitario"]

        base = _ficha(item, ingredientes_por_receta, con_opciones=con_opciones)
        base.pop("precio")
        productos.append(
            {
                **base,
                "categoria_id": item.get("categoria_id"),
                "precio_desde": precio_desde,
                "foto_url": fotos_uc.foto_principal_url(
                    session, entidad="producto", entidad_id=item["producto_comercial_id"]
                ),
                "variantes": variantes,
            }
        )

    return {
        "categorias": [{"id": cid, "nombre": nom} for cid, nom in categorias.items()],
        "productos": productos,
    }


def producto(session, producto_id: uuid.UUID) -> dict:
    datos = carta(session, con_opciones=True)
    for item in datos["productos"]:
        if item["id"] != producto_id:
            continue
        fotos = fotos_uc.listar(session, entidad="producto", entidad_id=producto_id)
        item["fotos"] = [f.url_storage for f in fotos]
        ids_ingrediente = [i["id"] for i in item["ingredientes"]]
        detalle = articulos_publicos(session, ids_ingrediente)
        item["ingredientes_detalle"] = [
            {
                "id": ing_id,
                "nombre": datos_ing["nombre"],
                "descripcion": datos_ing["descripcion"],
                "foto_url": fotos_uc.foto_principal_url(
                    session, entidad="ingrediente", entidad_id=ing_id
                ),
            }
            for ing_id, datos_ing in detalle.items()
        ]
        return item
    raise NoEncontrado("producto no encontrado")


def ingrediente(session, articulo_id: uuid.UUID) -> dict:
    detalle = articulos_publicos(session, [articulo_id])
    datos = detalle.get(articulo_id)
    if datos is None:
        raise NoEncontrado("insumo no encontrado")
    return {
        "id": articulo_id,
        "nombre": datos["nombre"],
        "descripcion": datos["descripcion"],
        "foto_url": fotos_uc.foto_principal_url(
            session, entidad="ingrediente", entidad_id=articulo_id
        ),
    }


def sucursales(session) -> list[dict]:
    marca_id = _marca_id()
    # `fechas.ahora()`: el horario de atención es local a Tarapoto
    # (America/Lima), no UTC — un "abierto" calculado en UTC diría cerrado
    # a las 6pm hora Perú, que es exactamente cuando abre.
    ahora = fechas.ahora()
    return [
        {**s, "abierto_ahora": abierto_ahora(s.get("horario_atencion"), ahora)}
        for s in sucursales_publicas_de_marca(session, marca_id)
    ]


def promociones(session) -> list[dict]:
    marca_id = _marca_id()
    empresas = empresas_de_marca(session, marca_id)
    return promociones_web_vigentes(
        session, empresa_ids=empresas, marca_id=marca_id, hoy=fechas.hoy()
    )


def convocatorias(session) -> list[dict]:
    marca_id = _marca_id()
    empresas = empresas_de_marca(session, marca_id)
    base = settings.storefront_url_postular_base.rstrip("/")
    return [
        {**conv, "url_postular": f"{base}/{conv['token']}"}
        for conv in convocatorias_publicadas(session, empresa_ids=empresas, hoy=fechas.hoy())
    ]
