"""Casos de uso de catálogo comercial: productos vendibles y medios de pago.

Un producto comercial puede ser tres cosas, y la diferencia es estructural,
no un enum:

- **Producto simple**: tiene receta y precio, se vende tal cual.
- **Producto con variantes**: no tiene receta ni se vende; sus hijos
  (`producto_padre_id`) son los que llevan receta y precio. Elegir uno es
  obligatorio en el PDV (RN-COM-022).
- **Extra** (`es_extra=True`): no sale suelto en la carta, se agrega a otro
  producto y su obligatoriedad la decide el grupo al que pertenece
  (RN-COM-023).

`receta_id` se valida contra el contrato público de `inventory`
(`queries_publicas`), nunca importando su ORM.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from src.modules.inventory.application.queries_publicas import (
    insumos_de_receta,
    receta_resumen,
)
from src.modules.sales.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.sales.infrastructure.models import (
    AtributoValor,
    MedioPago,
    ProductoAtributoLinea,
    ProductoAtributoValor,
    ProductoComercial,
    ProductoExclusion,
    ProductoOpcionGrupo,
)
from src.modules.sales.infrastructure.repositories import (
    MedioPagoRepo,
    ProductoComercialRepo,
)
from src.modules.users.infrastructure.models import Marca
from src.shared.texto import a_titulo

#: El otro extremo de la exclusión. Alias porque la tabla se une dos
#: veces contra `producto_atributo_valor`: una por cada lado del par.
_EXCLUIDO = aliased(ProductoAtributoValor)


def crear_producto(
    session: Session,
    *,
    id_interno: str,
    marca_id: uuid.UUID,
    nombre: str,
    receta_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    producto_padre_id: uuid.UUID | None = None,
    orden: int = 0,
    empaque_id: uuid.UUID | None = None,
    modalidades_empaque: list | None = None,
    es_extra: bool = False,
) -> ProductoComercial:
    repo = ProductoComercialRepo(session)
    if repo.get_by_id_interno(id_interno):
        raise Conflicto(f"id_interno '{id_interno}' ya existe")
    if receta_id is not None and receta_resumen(session, receta_id) is None:
        raise NoEncontrado("receta no encontrada")
    if producto_padre_id is not None:
        padre = _exigir(repo, producto_padre_id, "producto padre")
        _validar_padre(padre, receta_id, es_extra)
        marca_id = padre.marca_id
        categoria_id = categoria_id or padre.categoria_id
    return repo.add(
        ProductoComercial(
            id_interno=id_interno,
            marca_id=marca_id,
            nombre=a_titulo(nombre),
            receta_id=receta_id,
            categoria_id=categoria_id,
            producto_padre_id=producto_padre_id,
            orden=orden,
            empaque_id=empaque_id,
            modalidades_empaque=modalidades_empaque,
            es_extra=es_extra,
        )
    )


def _validar_padre(
    padre: ProductoComercial, receta_id: uuid.UUID | None, es_extra: bool
) -> None:
    """Reglas de la variante (RN-COM-022). Ninguna la puede hacer cumplir la
    base: padre e hijo son la misma tabla."""
    if es_extra:
        raise Conflicto("un extra no puede ser variante de otro producto")
    if padre.es_extra:
        raise Conflicto("un extra no admite variantes")
    if padre.producto_padre_id is not None:
        raise Conflicto(
            f"'{padre.nombre}' ya es una variante: no admite variantes propias"
        )
    if padre.receta_id is not None:
        raise Conflicto(
            f"'{padre.nombre}' tiene receta propia. Un producto con variantes no "
            "se prepara ni se vende por sí mismo: quítale la receta y pásala a "
            "su primera variante"
        )
    if receta_id is None:
        raise ReglaNegocio("una variante necesita su propia receta")


def crear_grupo_opcion(
    session: Session,
    *,
    producto_id: uuid.UUID,
    nombre: str,
    minimo: int = 0,
    maximo: int | None = None,
    orden: int = 0,
) -> ProductoOpcionGrupo:
    """Agrupa extras y define cuántos hay que elegir (RN-COM-023)."""
    repo = ProductoComercialRepo(session)
    producto = _exigir(repo, producto_id, "producto")
    nombre = a_titulo(nombre)
    if any(g.nombre == nombre for g in repo.grupos_de(producto_id)):
        raise Conflicto(f"'{producto.nombre}' ya tiene un grupo '{nombre}'")
    if minimo < 0:
        raise ReglaNegocio("el mínimo no puede ser negativo")
    if maximo is not None and maximo < max(minimo, 1):
        raise ReglaNegocio("el máximo del grupo no puede ser menor que su mínimo")
    return repo.add_grupo(
        ProductoOpcionGrupo(
            producto_comercial_id=producto_id,
            nombre=nombre,
            minimo=minimo,
            maximo=maximo,
            orden=orden,
        )
    )


def vincular_extra(
    session: Session,
    *,
    producto_id: uuid.UUID,
    extra_id: uuid.UUID,
    maximo: int | None = None,
    grupo_id: uuid.UUID | None = None,
):
    """Habilita un extra sobre un producto (RN-COM-021).

    Se valida acá y no en el esquema porque las dos puntas son la misma
    tabla: nada a nivel de FK impide colgar una pizza de otra pizza.
    """
    repo = ProductoComercialRepo(session)
    producto = repo.get(producto_id)
    extra = repo.get(extra_id)
    if producto is None:
        raise NoEncontrado("producto no encontrado")
    if extra is None:
        raise NoEncontrado("extra no encontrado")
    if not extra.es_extra:
        raise Conflicto(f"{extra.nombre} no está marcado como extra")
    if producto.es_extra:
        raise Conflicto("un extra no admite extras")
    if repo.admite_extra(producto_id, extra_id) is not None:
        raise Conflicto(f"{producto.nombre} ya admite ese extra")
    if grupo_id is not None:
        grupo = repo.get_grupo(grupo_id)
        if grupo is None or grupo.producto_comercial_id != producto_id:
            raise NoEncontrado("grupo de opciones no encontrado en este producto")
    return repo.vincular_extra(producto_id, extra_id, maximo, grupo_id)


def quitables_de(session: Session, producto_id: uuid.UUID) -> list[dict]:
    """Qué se le puede pedir "sin" a este producto (RN-PRD-004).

    Es la lista de insumos de su receta, sin nada que configurar aparte: una
    tabla de "quitables" repetiría lo que la receta ya dice, y dos datos que
    dicen lo mismo terminan diciendo cosas distintas.

    Endpoint aparte y no un campo de `GET /carta` a propósito: la carta se
    pide entera al abrir el PDV y esto haría una consulta de receta por
    producto para algo que el cajero mira en una línea a la vez. Se pide
    cuando abre el configurador de esa línea.
    """
    repo = ProductoComercialRepo(session)
    producto = _exigir(repo, producto_id, "producto comercial")
    if producto.receta_id is None:
        # El padre de un grupo de variantes no se prepara: lo quitable sale
        # de la variante elegida, y el PDV pregunta por esa.
        return []
    return [
        {"articulo_id": i["articulo_id"], "nombre": i["nombre"]}
        for i in insumos_de_receta(session, producto.receta_id)
    ]


def desvincular_extra(
    session: Session, *, producto_id: uuid.UUID, extra_id: uuid.UUID
) -> None:
    """Deja de ofrecer un extra en un producto.

    Borra el vínculo, no el extra: "extra queso" es un producto comercial
    con su receta y su precio, y lo siguen ofreciendo otros platos. Las
    ventas pasadas no se tocan — `venta_item` guarda su propio precio y su
    propia línea, así que el histórico no depende de esta tabla.
    """
    repo = ProductoComercialRepo(session)
    vinculo = repo.admite_extra(producto_id, extra_id)
    if vinculo is None:
        raise NoEncontrado("el producto no ofrece ese extra")
    repo.borrar_vinculo_extra(vinculo)


def borrar_grupo_opcion(
    session: Session, *, producto_id: uuid.UUID, grupo_id: uuid.UUID
) -> None:
    """Borra un grupo de opciones y suelta sus extras (siguen ofreciéndose,
    ahora sin obligatoriedad). Se exige que el grupo sea del producto de la
    ruta: un id de grupo suelto no debe poder borrar el grupo de otro."""
    repo = ProductoComercialRepo(session)
    grupo = repo.get_grupo(grupo_id)
    if grupo is None or grupo.producto_comercial_id != producto_id:
        raise NoEncontrado("grupo de opciones no encontrado en este producto")
    repo.borrar_grupo(grupo)


def editar_producto(session: Session, producto_id: uuid.UUID, **campos) -> ProductoComercial:
    repo = ProductoComercialRepo(session)
    prod = _exigir(repo, producto_id, "producto comercial")
    if campos.get("nombre") is not None:
        prod.nombre = a_titulo(campos["nombre"])
    if campos.get("quitar_receta"):
        _quitar_receta(prod)
    if campos.get("receta_id") is not None:
        if receta_resumen(session, campos["receta_id"]) is None:
            raise NoEncontrado("receta no encontrada")
        if repo.variantes_de(producto_id):
            raise Conflicto(
                f"'{prod.nombre}' tiene variantes: la receta va en cada una"
            )
        prod.receta_id = campos["receta_id"]
    for campo in (
        "activo", "categoria_id", "orden", "empaque_id", "modalidades_empaque",
    ):
        if campos.get(campo) is not None:
            setattr(prod, campo, campos[campo])
    return prod


def _quitar_receta(prod: ProductoComercial) -> None:
    """Deja al producto sin receta, que es el paso previo a venderlo por
    presentaciones (RN-COM-022): mientras tenga la suya, se vende tal cual.

    En una presentación no se permite: una variante sin receta no se puede
    preparar ni vender, y quedaría muerta dentro de su padre. La receta que
    se suelta no se borra — sigue en el módulo de recetas, lista para
    asignarse a la primera presentación.
    """
    if prod.producto_padre_id is not None:
        raise Conflicto(
            f"'{prod.nombre}' es una presentación: sin receta no se podría "
            "preparar. Cámbiala por otra o borra la presentación"
        )
    if prod.es_extra:
        raise Conflicto(f"'{prod.nombre}' es un extra: sin receta no se puede agregar")
    prod.receta_id = None


def eliminar_producto(session: Session, producto_id: uuid.UUID) -> None:
    """Borra un producto que nunca se vendió (una presentación cargada por
    error, típicamente).

    Si ya se vendió no se borra: `venta_item` guarda a qué producto
    corresponde cada línea, y romper eso reescribiría ventas pasadas. En ese
    caso se descontinúa (`activo=False`), que es lo que el modelo de datos
    manda para un producto con historia (RN-GEN-006).
    """
    repo = ProductoComercialRepo(session)
    prod = _exigir(repo, producto_id, "producto comercial")
    if repo.tiene_ventas(producto_id):
        raise Conflicto(
            f"'{prod.nombre}' ya se vendió: no se borra, se descontinúa "
            "(desmarca 'Activo') para no reescribir ventas pasadas"
        )
    if repo.variantes_de(producto_id):
        raise Conflicto(
            f"'{prod.nombre}' tiene presentaciones: bórralas primero"
        )
    repo.borrar_con_dependencias(prod)


def listar_productos(
    session: Session, marca_id: uuid.UUID | None = None
) -> list[ProductoComercial]:
    return ProductoComercialRepo(session).list(marca_id)


def listar_marcas(session: Session) -> list[dict]:
    """Marcas a las que se le puede colgar un producto.

    Sin filtro de tenant: la marca pertenece al grupo, no a una empresa
    (`marca.grupo_id`), y hoy el grupo es uno solo. El día que haya dos
    grupos operando en la misma instalación, el filtro entra acá —no en la
    pantalla, que no puede hacerlo cumplir.
    """
    return [
        {"id": m.id, "nombre": m.nombre, "tipo": m.tipo}
        for m in session.scalars(
            select(Marca).where(Marca.deleted_at.is_(None)).order_by(Marca.nombre)
        )
    ]


def detalle_producto(session: Session, producto_id: uuid.UUID) -> dict:
    """La ficha completa que edita la pantalla de catálogo: el producto, sus
    variantes y sus grupos de extras con lo que cada uno admite."""
    repo = ProductoComercialRepo(session)
    producto = _exigir(repo, producto_id, "producto comercial")
    grupos = repo.grupos_de(producto_id)
    extras_por_grupo: dict[uuid.UUID | None, list] = {}
    for vinculo in repo.extras_de(producto_id):
        extra = repo.get(vinculo.extra_id)
        if extra is None:
            continue
        extras_por_grupo.setdefault(vinculo.grupo_id, []).append(
            {
                "extra_id": extra.id,
                "nombre": extra.nombre,
                "receta_id": extra.receta_id,
                "maximo": vinculo.maximo,
            }
        )
    return {
        **_producto_dict(producto),
        "variantes": [_producto_dict(v) for v in repo.variantes_de(producto_id)],
        "grupos": [
            {
                "id": g.id,
                "nombre": g.nombre,
                "minimo": g.minimo,
                "maximo": g.maximo,
                "orden": g.orden,
                "extras": extras_por_grupo.get(g.id, []),
            }
            for g in grupos
        ],
        # Extras habilitados sin grupo: siempre opcionales.
        "extras_sueltos": extras_por_grupo.get(None, []),
    }


def _producto_dict(p: ProductoComercial) -> dict:
    return {
        "id": p.id,
        "id_interno": p.id_interno,
        "marca_id": p.marca_id,
        "nombre": p.nombre,
        "categoria_id": p.categoria_id,
        "receta_id": p.receta_id,
        "producto_padre_id": p.producto_padre_id,
        "orden": p.orden,
        "activo": p.activo,
        "es_extra": p.es_extra,
        "empaque_id": p.empaque_id,
        "modalidades_empaque": p.modalidades_empaque,
    }


def _exigir(
    repo: ProductoComercialRepo, producto_id: uuid.UUID, que: str
) -> ProductoComercial:
    producto = repo.get(producto_id)
    if producto is None:
        raise NoEncontrado(f"{que} no encontrado")
    return producto


def crear_medio_pago(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    direccion: str,
    tipo: str,
    comision_pct: Decimal = Decimal(0),
) -> MedioPago:
    return MedioPagoRepo(session).add(
        MedioPago(
            empresa_id=empresa_id,
            nombre=nombre,
            direccion=direccion,
            tipo=tipo,
            comision_pct=comision_pct,
        )
    )


def listar_medios_pago(
    session: Session, empresa_id: uuid.UUID | None = None
) -> list[MedioPago]:
    return MedioPagoRepo(session).list(empresa_id)


def valores_ofrecidos(session: Session, producto: ProductoComercial) -> set[str]:
    """`producto_atributo_valor.id` (texto) que este producto puede recibir.

    **Lo propio más lo del padre**, exactamente como `grupos_efectivos` y
    `extras_efectivos` (ADR-042). La razón es la misma y ya costó dos
    correcciones: quien arma un producto a mano cuelga el atributo del padre
    —porque cuando lo crea todavía no hay variantes—, y el importador lo
    cuelga donde diga la planilla. Mientras el lugar importe, siempre hay
    una mitad de los catálogos rota.

    Solo valores activos: retirar un valor tiene que sacarlo de la oferta sin
    romper las ventas viejas que lo nombran.
    """
    productos = [producto.id]
    if producto.producto_padre_id is not None:
        productos.append(producto.producto_padre_id)
    filas = session.scalars(
        select(ProductoAtributoValor.id)
        .join(
            ProductoAtributoLinea,
            ProductoAtributoValor.linea_id == ProductoAtributoLinea.id,
        )
        .where(
            ProductoAtributoLinea.producto_comercial_id.in_(productos),
            ProductoAtributoValor.activo.is_(True),
        )
    )
    return {str(v) for v in filas}


def combinacion_excluida(
    session: Session, valor_ids: Sequence[str]
) -> tuple[str, str] | None:
    """El primer par de valores elegidos que no pueden ir juntos, o `None`.

    Es `product.template.attribute.exclusion` de Odoo, y el caso que lo hace
    obligatorio en Charlie's es la pizza mitad-y-mitad: **las dos mitades
    tienen que ser distintas**. Media hawaiana y media hawaiana no es una
    mitad-y-mitad, es una hawaiana entera — que ya se vende como su propio
    producto, con su receta y su precio.

    La exclusión se guarda una vez y se lee en los dos sentidos: son el mismo
    hecho, y guardar las dos filas sería la primera en desincronizarse.

    Devuelve los **nombres** y no los ids porque lo único que se hace con
    esto es escribir el mensaje de error, y un mensaje con dos UUID no le
    dice nada al cajero.
    """
    if len(valor_ids) < 2:
        return None
    ids = [uuid.UUID(str(v)) for v in valor_ids]
    izquierda = aliased(AtributoValor)
    derecha = aliased(AtributoValor)
    fila = session.execute(
        select(izquierda.nombre, derecha.nombre)
        .select_from(ProductoExclusion)
        .join(
            ProductoAtributoValor,
            ProductoExclusion.producto_atributo_valor_id == ProductoAtributoValor.id,
        )
        .join(izquierda, ProductoAtributoValor.atributo_valor_id == izquierda.id)
        .join(
            _EXCLUIDO,
            ProductoExclusion.excluye_valor_id == _EXCLUIDO.id,
        )
        .join(derecha, _EXCLUIDO.atributo_valor_id == derecha.id)
        .where(
            ProductoExclusion.producto_atributo_valor_id.in_(ids),
            ProductoExclusion.excluye_valor_id.in_(ids),
        )
        .limit(1)
    ).first()
    return (fila[0], fila[1]) if fila else None
