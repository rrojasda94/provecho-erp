"""Repositorios SQLAlchemy del módulo inventory. La sesión es la Unit of Work."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    CategoriaUdm,
    Conteo,
    ConteoItem,
    Devolucion,
    DevolucionItem,
    GuiaRemision,
    GuiaRemisionItem,
    Lote,
    MovimientoInventario,
    Receta,
    RecetaItem,
    ReservaStock,
    Sku,
    SolicitudInsumos,
    SolicitudItem,
    Stock,
    StockLote,
    Transferencia,
    TransferenciaItem,
    UnidadMedida,
)
from src.modules.users.infrastructure.models import Almacen, Sucursal


def _acotar_por_almacen(
    q,
    columna_almacen,
    empresa_id: uuid.UUID | None,
    sucursal_id: uuid.UUID | None = None,
    marca_id: uuid.UUID | None = None,
):
    """Acota una consulta por empresa, sucursal o marca a través del almacén.

    Las tres viven arriba del almacén (`almacen.empresa_id`,
    `almacen.sucursal_id`, `sucursal.marca_id`), así que un solo join
    responde las tres preguntas y ninguna necesita columna nueva en las
    tablas que se filtran.
    """
    if empresa_id is None and sucursal_id is None and marca_id is None:
        return q
    q = q.join(Almacen, Almacen.id == columna_almacen)
    if empresa_id is not None:
        q = q.where(Almacen.empresa_id == empresa_id)
    if sucursal_id is not None:
        q = q.where(Almacen.sucursal_id == sucursal_id)
    if marca_id is not None:
        q = q.join(Sucursal, Sucursal.id == Almacen.sucursal_id).where(
            Sucursal.marca_id == marca_id
        )
    return q


class ArticuloRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, articulo_id: uuid.UUID) -> Articulo | None:
        return self.s.get(Articulo, articulo_id)

    def get_by_id_interno(self, id_interno: str) -> Articulo | None:
        return self.s.scalar(select(Articulo).where(Articulo.id_interno == id_interno))

    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        tipo: str | list[str] | None = None,
        busqueda: str | None = None,
    ):
        """La consulta, sin ejecutar: el router la pagina (ADR-026).

        `tipo` filtra en la base y no en el cliente porque la lista viene
        paginada: una pantalla que solo quiere empaques y filtra lo que le
        llegó se queda sin ninguno en cuanto el catálogo pasa de una página
        —y no muestra "faltan", muestra un desplegable vacío.

        `busqueda` existe por lo mismo, y es el único catálogo que la necesita:
        con miles de artículos y un techo de 200 filas por página, un
        desplegable que filtre lo que ya recibió deja invisible casi todo el
        catálogo sin decirlo. Se busca por nombre y por `id_interno` porque
        quien tiene el código a mano lo teclea en vez del nombre.
        """
        q = select(Articulo).where(Articulo.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Articulo.empresa_id == empresa_id)
        # Acepta uno o varios: "qué se puede producir" son las subrecetas **y**
        # la mercadería, y resolverlo filtrando en la pantalla lo que llegó de
        # la primera página dejaba fuera casi todo el catálogo.
        if tipo is not None:
            tipos = [tipo] if isinstance(tipo, str) else list(tipo)
            q = q.where(Articulo.tipo.in_(tipos)) if tipos else q
        if busqueda:
            patron = f"%{busqueda}%"
            q = q.where(Articulo.nombre.ilike(patron) | Articulo.id_interno.ilike(patron))
        return q.order_by(Articulo.nombre)

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Articulo]:
        return list(self.s.scalars(self.q_list(empresa_id)))

    def add(self, articulo: Articulo) -> Articulo:
        self.s.add(articulo)
        self.s.flush()
        return articulo


class RecetaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, receta_id: uuid.UUID) -> Receta | None:
        return self.s.get(Receta, receta_id)

    def get_by_nombre(self, nombre: str, empresa_id: uuid.UUID) -> Receta | None:
        """El nombre es único **por empresa**: que Majambo tenga una "Pizza
        Margarita" no puede impedirle a otra empresa del grupo tener la
        suya."""
        return self.s.scalar(
            select(Receta).where(
                Receta.nombre == nombre, Receta.empresa_id == empresa_id
            )
        )

    def list(
        self,
        empresa_id: uuid.UUID | None = None,
        *,
        tipo: str | None = None,
        categoria_id: uuid.UUID | None = None,
    ) -> list[Receta]:
        """`tipo` no es una columna: se **deriva** de `articulo_id`
        (RN-COM-030). Una receta que produce un artículo es una subreceta —
        se guarda para usarla en otra—; una que no, es un producto de venta.
        Agregar la columna sería un segundo lugar donde puede estar mal.

        `categoria_id` filtra por la categoría del artículo que produce, así
        que solo alcanza a las subrecetas — es lo correcto: un producto de
        venta no tiene artículo del que sacar categoría.
        """
        q = select(Receta).order_by(Receta.nombre)
        if empresa_id is not None:
            q = q.where(Receta.empresa_id == empresa_id)
        if tipo == "subreceta":
            q = q.where(Receta.articulo_id.is_not(None))
        elif tipo == "producto":
            q = q.where(Receta.articulo_id.is_(None))
        if categoria_id is not None:
            q = q.join(Articulo, Articulo.id == Receta.articulo_id).where(
                Articulo.categoria_id == categoria_id
            )
        return list(self.s.scalars(q))

    def add(self, receta: Receta) -> Receta:
        self.s.add(receta)
        self.s.flush()
        return receta

    # Anotación entre comillas: `list` está sombreado por el método de arriba.
    def items(self, receta_id: uuid.UUID) -> "list[RecetaItem]":
        return [
            *self.s.scalars(
                select(RecetaItem)
                .where(RecetaItem.receta_id == receta_id)
                .order_by(RecetaItem.created_at, RecetaItem.id)
            )
        ]

    def get_item(self, item_id: uuid.UUID) -> RecetaItem | None:
        return self.s.get(RecetaItem, item_id)

    def add_item(self, item: RecetaItem) -> RecetaItem:
        self.s.add(item)
        self.s.flush()
        return item

    def borrar_item(self, item: RecetaItem) -> None:
        self.s.delete(item)


class CategoriaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, categoria_id: uuid.UUID) -> Categoria | None:
        return self.s.get(Categoria, categoria_id)

    def get_by_nombre(self, empresa_id: uuid.UUID, nombre: str) -> Categoria | None:
        return self.s.scalar(
            select(Categoria).where(
                Categoria.empresa_id == empresa_id, Categoria.nombre == nombre
            )
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> list[Categoria]:
        q = select(Categoria).where(Categoria.deleted_at.is_(None))
        if empresa_id is not None:
            q = q.where(Categoria.empresa_id == empresa_id)
        return list(self.s.scalars(q.order_by(Categoria.nombre)))

    def add(self, categoria: Categoria) -> Categoria:
        self.s.add(categoria)
        self.s.flush()
        return categoria


class CategoriaUdmRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, categoria_udm_id: uuid.UUID) -> CategoriaUdm | None:
        return self.s.get(CategoriaUdm, categoria_udm_id)

    def get_by_nombre(self, nombre: str) -> CategoriaUdm | None:
        return self.s.scalar(select(CategoriaUdm).where(CategoriaUdm.nombre == nombre))

    def list(self) -> list[CategoriaUdm]:
        return list(self.s.scalars(select(CategoriaUdm).order_by(CategoriaUdm.nombre)))

    def add(self, categoria: CategoriaUdm) -> CategoriaUdm:
        self.s.add(categoria)
        self.s.flush()
        return categoria


class UnidadMedidaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, unidad_medida_id: uuid.UUID) -> UnidadMedida | None:
        return self.s.get(UnidadMedida, unidad_medida_id)

    def get_by_nombre(
        self, categoria_udm_id: uuid.UUID, nombre: str
    ) -> UnidadMedida | None:
        return self.s.scalar(
            select(UnidadMedida).where(
                UnidadMedida.categoria_udm_id == categoria_udm_id,
                UnidadMedida.nombre == nombre,
            )
        )

    def list(self) -> list[UnidadMedida]:
        # Global: sin filtro de empresa (RN-GER-010, docstring del modelo).
        return list(self.s.scalars(select(UnidadMedida).order_by(UnidadMedida.nombre)))

    def add(self, unidad: UnidadMedida) -> UnidadMedida:
        self.s.add(unidad)
        self.s.flush()
        return unidad


class SkuRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, sku_id: uuid.UUID) -> Sku | None:
        return self.s.get(Sku, sku_id)

    def get_by_codigo(self, codigo: str) -> Sku | None:
        return self.s.scalar(select(Sku).where(Sku.codigo == codigo))

    def tiene_alguno(self, articulo_id: uuid.UUID) -> bool:
        """Si el artículo ya tiene SKU. Lo pregunta `catalogo.asegurar_sku`
        antes de crear el suyo por defecto (RN-PRD-006)."""
        return (
            self.s.scalar(
                select(Sku.id).where(Sku.articulo_id == articulo_id).limit(1)
            )
            is not None
        )

    def list(self, empresa_id: uuid.UUID | None = None) -> "list[tuple[Sku, Articulo]]":
        """SKUs con el artículo que representan.

        Van juntos porque el código de un SKU no le dice nada a nadie: para
        elegir qué se devuelve hay que ver "Queso Mozzarella", no
        "SKU-I003-Queso Mo".
        """
        q = (
            select(Sku, Articulo)
            .join(Articulo, Articulo.id == Sku.articulo_id)
            .order_by(Articulo.nombre)
        )
        if empresa_id is not None:
            q = q.where(Articulo.empresa_id == empresa_id)
        return list(self.s.execute(q))

    def add(self, sku: Sku) -> Sku:
        self.s.add(sku)
        self.s.flush()
        return sku


class StockRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(
        self, almacen_id: uuid.UUID, sku_id: uuid.UUID, for_update: bool = False
    ) -> Stock | None:
        q = select(Stock).where(
            Stock.almacen_id == almacen_id, Stock.sku_id == sku_id
        )
        if for_update:
            # Bloqueo de fila para evitar lost-update en movimientos
            # concurrentes (no-op en SQLite; efectivo en Postgres).
            q = q.with_for_update()
        return self.s.scalar(q)

    def q_list(
        self,
        almacen_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        *,
        sucursal_id: uuid.UUID | None = None,
        categoria_id: uuid.UUID | None = None,
        bajo_minimo: bool | None = None,
        q: str | None = None,
    ):
        consulta = select(Stock)
        if almacen_id is not None:
            consulta = consulta.where(Stock.almacen_id == almacen_id)
        if sku_id is not None:
            consulta = consulta.where(Stock.sku_id == sku_id)
        if empresa_id is not None or sucursal_id is not None:
            # El stock no lleva empresa ni sucursal: las hereda del almacén
            # (ADR-004). Un solo join sirve a las dos.
            consulta = consulta.join(Almacen, Almacen.id == Stock.almacen_id)
            if empresa_id is not None:
                consulta = consulta.where(Almacen.empresa_id == empresa_id)
            if sucursal_id is not None:
                consulta = consulta.where(Almacen.sucursal_id == sucursal_id)
        if categoria_id is not None or q:
            # La categoría y el nombre son del artículo, dos saltos más
            # arriba: `stock` habla de SKU y el SKU cuelga del artículo.
            consulta = consulta.join(Sku, Sku.id == Stock.sku_id).join(
                Articulo, Articulo.id == Sku.articulo_id
            )
            if categoria_id is not None:
                consulta = consulta.where(Articulo.categoria_id == categoria_id)
            if q:
                patron = f"%{q.strip()}%"
                consulta = consulta.where(
                    or_(Articulo.nombre.ilike(patron), Sku.codigo.ilike(patron))
                )
        if bajo_minimo:
            # La misma condición que `rules.stock_bajo`, expresada en SQL —
            # traerse la tabla entera para filtrar en Python es lo que
            # `contar_bajo_minimo` ya dejó de hacer.
            consulta = consulta.where(
                Stock.stock_minimo.is_not(None), Stock.cantidad <= Stock.stock_minimo
            )
        # Orden estable: sin él, dos páginas seguidas pueden repetir u
        # omitir filas (Postgres no promete orden sin `ORDER BY`).
        return consulta.order_by(Stock.almacen_id, Stock.sku_id)

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
    ) -> list[Stock]:
        return list(self.s.scalars(self.q_list(almacen_id, empresa_id, sku_id)))

    def add(self, stock: Stock) -> Stock:
        self.s.add(stock)
        self.s.flush()
        return stock


class MovimientoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, mov: MovimientoInventario) -> MovimientoInventario:
        self.s.add(mov)
        self.s.flush()
        return mov

    def hubo_alguno(self, almacen_id: uuid.UUID, sku_id: uuid.UUID) -> bool:
        """Si ese SKU ya se movió alguna vez en ese almacén. Lo pregunta la
        carga inicial, que solo vale mientras no haya historia
        (`rules.carga_inicial_permitida`)."""
        return (
            self.s.scalar(
                select(MovimientoInventario.id)
                .where(
                    MovimientoInventario.almacen_id == almacen_id,
                    MovimientoInventario.sku_id == sku_id,
                )
                .limit(1)
            )
            is not None
        )

    def q_list(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ):
        """El kardex, de lo más reciente a lo más viejo.

        Los tres filtros son opcionales porque la pregunta de la pantalla no
        siempre es la misma: «qué pasó con este SKU acá» al abrir una ficha,
        «qué se movió hoy en este almacén» al cuadrar el día.

        El orden se invirtió respecto de la consulta original —que nadie
        llegó a usar—: quien mira un kardex quiere el último movimiento
        arriba, y con paginación el orden ascendente dejaba lo importante en
        la última página.
        """
        consulta = select(MovimientoInventario)
        if almacen_id is not None:
            consulta = consulta.where(MovimientoInventario.almacen_id == almacen_id)
        if sku_id is not None:
            consulta = consulta.where(MovimientoInventario.sku_id == sku_id)
        if empresa_id is not None:
            # El movimiento hereda la empresa de su almacén (ADR-004).
            consulta = consulta.join(
                Almacen, Almacen.id == MovimientoInventario.almacen_id
            ).where(Almacen.empresa_id == empresa_id)
        # `id` desempata: dos movimientos del mismo `ts` (una salida FEFO
        # repartida entre lotes se inserta en el mismo instante) se
        # ordenarían distinto en cada página.
        return consulta.order_by(
            MovimientoInventario.ts.desc(), MovimientoInventario.id.desc()
        )

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[MovimientoInventario]:
        return list(self.s.scalars(self.q_list(almacen_id, sku_id, empresa_id)))


class LoteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, lote_id: uuid.UUID) -> Lote | None:
        return self.s.get(Lote, lote_id)

    def get_by_codigo(self, articulo_id: uuid.UUID, codigo: str) -> Lote | None:
        return self.s.scalar(
            select(Lote).where(Lote.articulo_id == articulo_id, Lote.codigo == codigo)
        )

    def add(self, lote: Lote) -> Lote:
        self.s.add(lote)
        self.s.flush()
        return lote


class StockLoteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(
        self,
        almacen_id: uuid.UUID,
        sku_id: uuid.UUID,
        lote_id: uuid.UUID,
        for_update: bool = False,
    ) -> StockLote | None:
        q = select(StockLote).where(
            StockLote.almacen_id == almacen_id,
            StockLote.sku_id == sku_id,
            StockLote.lote_id == lote_id,
        )
        if for_update:
            q = q.with_for_update()
        return self.s.scalar(q)

    def fefo(self, almacen_id: uuid.UUID, sku_id: uuid.UUID) -> list[StockLote]:
        """Lotes con saldo, ordenados por vencimiento más próximo; los que no
        vencen van al final y entre ellos manda el más antiguo (FIFO)."""
        return list(
            self.s.scalars(
                select(StockLote)
                .join(Lote, Lote.id == StockLote.lote_id)
                .where(
                    StockLote.almacen_id == almacen_id,
                    StockLote.sku_id == sku_id,
                    StockLote.cantidad > 0,
                )
                .order_by(
                    Lote.fecha_vencimiento.is_(None),
                    Lote.fecha_vencimiento,
                    Lote.created_at,
                )
            )
        )

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[tuple[StockLote, Lote]]:
        q = select(StockLote, Lote).join(Lote, Lote.id == StockLote.lote_id)
        if almacen_id is not None:
            q = q.where(StockLote.almacen_id == almacen_id)
        if sku_id is not None:
            q = q.where(StockLote.sku_id == sku_id)
        if empresa_id is not None:
            # El stock no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == StockLote.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return [
            (sl, lote)
            for sl, lote in self.s.execute(
                q.order_by(
                    Lote.fecha_vencimiento.is_(None), Lote.fecha_vencimiento
                )
            )
        ]

    def add(self, stock_lote: StockLote) -> StockLote:
        self.s.add(stock_lote)
        self.s.flush()
        return stock_lote


class AjusteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, ajuste_id: uuid.UUID) -> Ajuste | None:
        return self.s.get(Ajuste, ajuste_id)

    def add(self, ajuste: Ajuste) -> Ajuste:
        self.s.add(ajuste)
        self.s.flush()
        return ajuste


class ReservaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, reserva_id: uuid.UUID) -> ReservaStock | None:
        return self.s.get(ReservaStock, reserva_id)

    def activas(
        self,
        almacen_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[ReservaStock]:
        q = select(ReservaStock).where(ReservaStock.estado == "activa")
        if almacen_id is not None:
            q = q.where(ReservaStock.almacen_id == almacen_id)
        if sku_id is not None:
            q = q.where(ReservaStock.sku_id == sku_id)
        if empresa_id is not None:
            # La reserva no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == ReservaStock.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return list(self.s.scalars(q))

    def por_referencia(self, referencia_id: uuid.UUID) -> list[ReservaStock]:
        return list(
            self.s.scalars(
                select(ReservaStock).where(
                    ReservaStock.referencia_id == referencia_id,
                    ReservaStock.estado == "activa",
                )
            )
        )

    def add(self, reserva: ReservaStock) -> ReservaStock:
        self.s.add(reserva)
        self.s.flush()
        return reserva


class SolicitudRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, solicitud_id: uuid.UUID) -> SolicitudInsumos | None:
        return self.s.get(SolicitudInsumos, solicitud_id)

    def items(self, solicitud_id: uuid.UUID) -> list[SolicitudItem]:
        return list(
            self.s.scalars(
                select(SolicitudItem).where(SolicitudItem.solicitud_id == solicitud_id)
            )
        )

    def add(self, solicitud: SolicitudInsumos) -> SolicitudInsumos:
        self.s.add(solicitud)
        self.s.flush()
        return solicitud

    def add_item(self, item: SolicitudItem) -> SolicitudItem:
        self.s.add(item)
        self.s.flush()
        return item

    def borrador_de(self, almacen_id: uuid.UUID) -> SolicitudInsumos | None:
        """La lista que el almacén está juntando ahora (RN-INV-023). Uno por
        almacén, no por usuario: la jornada la levanta el turno completo."""
        return self.s.scalars(
            select(SolicitudInsumos).where(
                SolicitudInsumos.almacen_solicitante_id == almacen_id,
                SolicitudInsumos.estado == "borrador",
            )
        ).first()

    def item(
        self, solicitud_id: uuid.UUID, sku_id: uuid.UUID
    ) -> SolicitudItem | None:
        return self.s.scalar(
            select(SolicitudItem).where(
                SolicitudItem.solicitud_id == solicitud_id,
                SolicitudItem.sku_id == sku_id,
            )
        )

    def delete_item(self, item: SolicitudItem) -> None:
        self.s.delete(item)
        self.s.flush()

    # `list` va al final: nombrar así un método sombrea al builtin dentro
    # del cuerpo de la clase, y cualquier anotación `list[...]` que venga
    # después reventaría al evaluarse.
    def q_list(
        self,
        almacen_solicitante_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
        sucursal_id: uuid.UUID | None = None,
        marca_id: uuid.UUID | None = None,
        incluir_borradores: bool = False,
        almacen_abastecedor_id: uuid.UUID | None = None,
    ):
        q = select(SolicitudInsumos)
        if almacen_solicitante_id is not None:
            q = q.where(
                SolicitudInsumos.almacen_solicitante_id == almacen_solicitante_id
            )
        if almacen_abastecedor_id is not None:
            # La bandeja del que despacha. Faltaba: se podía preguntar "qué
            # pedí" pero no "qué me piden", y el central no tenía dónde ver su
            # cola de trabajo.
            q = q.where(
                SolicitudInsumos.almacen_abastecedor_id == almacen_abastecedor_id
            )
        if estado is not None:
            q = q.where(SolicitudInsumos.estado == estado)
        elif not incluir_borradores:
            # Un borrador todavía no le pidió nada a nadie: mismo criterio que
            # la OC en borrador de `purchases`. Se pide por su ruta propia.
            q = q.where(SolicitudInsumos.estado != "borrador")
        q = _acotar_por_almacen(
            q,
            SolicitudInsumos.almacen_solicitante_id,
            empresa_id,
            sucursal_id,
            marca_id,
        )
        return q.order_by(SolicitudInsumos.created_at.desc())

    def list(
        self,
        almacen_solicitante_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> "list[SolicitudInsumos]":
        return list(
            self.s.scalars(
                self.q_list(almacen_solicitante_id, estado, empresa_id)
            )
        )


class TransferenciaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, transferencia_id: uuid.UUID) -> Transferencia | None:
        return self.s.get(Transferencia, transferencia_id)

    def items(self, transferencia_id: uuid.UUID) -> list[TransferenciaItem]:
        return list(
            self.s.scalars(
                select(TransferenciaItem).where(
                    TransferenciaItem.transferencia_id == transferencia_id
                )
            )
        )

    def add(self, transferencia: Transferencia) -> Transferencia:
        self.s.add(transferencia)
        self.s.flush()
        return transferencia

    def add_item(self, item: TransferenciaItem) -> TransferenciaItem:
        self.s.add(item)
        self.s.flush()
        return item

    # Ver la nota de `SolicitudRepo.list`: este método sombrea al builtin.
    def q_list(
        self,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ):
        """`almacen_id` matchea origen o destino: quien mira un almacén
        quiere ver lo que sale y lo que le llega."""
        q = select(Transferencia)
        if almacen_id is not None:
            q = q.where(
                or_(
                    Transferencia.origen_almacen_id == almacen_id,
                    Transferencia.destino_almacen_id == almacen_id,
                )
            )
        if estado is not None:
            q = q.where(Transferencia.estado == estado)
        if empresa_id is not None:
            q = q.join(
                Almacen, Almacen.id == Transferencia.origen_almacen_id
            ).where(Almacen.empresa_id == empresa_id)
        return q.order_by(Transferencia.created_at.desc())

    def list(
        self,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> "list[Transferencia]":
        return list(self.s.scalars(self.q_list(almacen_id, estado, empresa_id)))


class GuiaRemisionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, guia_id: uuid.UUID) -> GuiaRemision | None:
        return self.s.get(GuiaRemision, guia_id)

    def de_transferencia(self, transferencia_id: uuid.UUID) -> GuiaRemision | None:
        return self.s.scalar(
            select(GuiaRemision).where(
                GuiaRemision.transferencia_id == transferencia_id
            )
        )

    def de_devolucion(self, devolucion_id: uuid.UUID) -> GuiaRemision | None:
        return self.s.scalar(
            select(GuiaRemision).where(GuiaRemision.devolucion_id == devolucion_id)
        )

    def items(self, guia_id: uuid.UUID) -> list[GuiaRemisionItem]:
        return list(
            self.s.scalars(
                select(GuiaRemisionItem).where(
                    GuiaRemisionItem.guia_remision_id == guia_id
                )
            )
        )

    def siguiente_correlativo(self, empresa_id: uuid.UUID, serie: str) -> int:
        """El correlativo es por (empresa, serie), que es como lo lleva SUNAT.

        Se calcula al emitir y no se reserva antes: una guía que no llegó a
        emitirse dejaría un hueco en la numeración, y un hueco hay que
        justificarlo ante una fiscalización.
        """
        actual = self.s.scalar(
            select(func.max(GuiaRemision.correlativo)).where(
                GuiaRemision.empresa_id == empresa_id, GuiaRemision.serie == serie
            )
        )
        return (actual or 0) + 1

    def add(self, guia: GuiaRemision) -> GuiaRemision:
        self.s.add(guia)
        self.s.flush()
        return guia

    def add_item(self, item: GuiaRemisionItem) -> GuiaRemisionItem:
        self.s.add(item)
        self.s.flush()
        return item

    # Ver la nota de `SolicitudRepo.list`: este método sombrea al builtin.
    def q_list(
        self,
        empresa_id: uuid.UUID | None = None,
        estado_emision: str | None = None,
    ):
        q = select(GuiaRemision)
        if empresa_id is not None:
            q = q.where(GuiaRemision.empresa_id == empresa_id)
        if estado_emision is not None:
            q = q.where(GuiaRemision.estado_emision == estado_emision)
        return q.order_by(GuiaRemision.created_at.desc())

    def pendientes(self, limite: int = 50) -> "list[GuiaRemision]":
        """Guías que quedaron sin respuesta de SUNAT. Es la red de seguridad
        de la cola: un worker caído deja la guía en `pendiente` y nada más
        la vuelve a mirar."""
        return list(
            self.s.scalars(
                select(GuiaRemision)
                .where(GuiaRemision.estado_emision.in_(("pendiente", "error")))
                .order_by(GuiaRemision.created_at)
                .limit(limite)
            )
        )


class ConteoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, conteo_id: uuid.UUID) -> Conteo | None:
        return self.s.get(Conteo, conteo_id)

    def abierto_en(
        self, almacen_id: uuid.UUID, categoria_id: uuid.UUID | None
    ) -> Conteo | None:
        """Conteo abierto que ya cubre esa categoría en ese almacén.

        Un conteo general abierto (categoria_id NULL) bloquea a todos: ya
        los está contando. Y abrir uno general con cualquier conteo abierto
        encima también choca — por eso el filtro se relaja a "cualquiera".
        """
        q = select(Conteo).where(
            Conteo.almacen_id == almacen_id, Conteo.estado == "abierto"
        )
        if categoria_id is not None:
            q = q.where(
                or_(
                    Conteo.categoria_id == categoria_id,
                    Conteo.categoria_id.is_(None),
                )
            )
        return self.s.scalars(q).first()

    def ultimo_cerrado(
        self, almacen_id: uuid.UUID, categoria_id: uuid.UUID
    ) -> Conteo | None:
        """Último conteo cerrado que cubrió esa categoría — el general
        (categoria_id NULL) también cuenta: contó todo el almacén."""
        return self.s.scalars(
            select(Conteo)
            .where(
                Conteo.almacen_id == almacen_id,
                Conteo.estado == "cerrado",
                or_(
                    Conteo.categoria_id == categoria_id,
                    Conteo.categoria_id.is_(None),
                ),
            )
            .order_by(Conteo.cerrado_at.desc())
        ).first()

    def items(self, conteo_id: uuid.UUID) -> list[ConteoItem]:
        return list(
            self.s.scalars(
                select(ConteoItem).where(ConteoItem.conteo_id == conteo_id)
            )
        )

    def item(self, conteo_id: uuid.UUID, sku_id: uuid.UUID) -> ConteoItem | None:
        return self.s.scalar(
            select(ConteoItem).where(
                ConteoItem.conteo_id == conteo_id, ConteoItem.sku_id == sku_id
            )
        )

    def add(self, conteo: Conteo) -> Conteo:
        self.s.add(conteo)
        self.s.flush()
        return conteo

    def add_item(self, item: ConteoItem) -> ConteoItem:
        self.s.add(item)
        self.s.flush()
        return item

    def q_list(
        self,
        almacen_id: uuid.UUID | None = None,
        estado: str | None = None,
        empresa_id: uuid.UUID | None = None,
        sucursal_id: uuid.UUID | None = None,
        marca_id: uuid.UUID | None = None,
    ):
        """Los conteos del almacén, sucursal o marca. El abierto primero: es
        el que alguien está contando y el único sobre el que se puede actuar."""
        q = select(Conteo)
        if almacen_id is not None:
            q = q.where(Conteo.almacen_id == almacen_id)
        if estado is not None:
            q = q.where(Conteo.estado == estado)
        q = _acotar_por_almacen(
            q, Conteo.almacen_id, empresa_id, sucursal_id, marca_id
        )
        return q.order_by(
            (Conteo.estado != "abierto"), Conteo.created_at.desc()
        )


class DevolucionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, devolucion_id: uuid.UUID) -> Devolucion | None:
        return self.s.get(Devolucion, devolucion_id)

    def items(self, devolucion_id: uuid.UUID) -> list[DevolucionItem]:
        return list(
            self.s.scalars(
                select(DevolucionItem).where(
                    DevolucionItem.devolucion_id == devolucion_id
                )
            )
        )

    def guia(self, devolucion_id: uuid.UUID) -> GuiaRemision | None:
        return self.s.scalar(
            select(GuiaRemision).where(GuiaRemision.devolucion_id == devolucion_id)
        )

    def listar(
        self,
        almacen_id: uuid.UUID | None = None,
        origen: str | None = None,
        empresa_id: uuid.UUID | None = None,
    ) -> list[Devolucion]:
        q = select(Devolucion).order_by(Devolucion.created_at.desc())
        if almacen_id is not None:
            q = q.where(Devolucion.almacen_id == almacen_id)
        if origen is not None:
            q = q.where(Devolucion.origen == origen)
        if empresa_id is not None:
            # La devolución no lleva empresa: la hereda del almacén (ADR-004).
            q = q.join(Almacen, Almacen.id == Devolucion.almacen_id).where(
                Almacen.empresa_id == empresa_id
            )
        return list(self.s.scalars(q))

    def add(self, devolucion: Devolucion) -> Devolucion:
        self.s.add(devolucion)
        self.s.flush()
        return devolucion

    def add_item(self, item: DevolucionItem) -> DevolucionItem:
        self.s.add(item)
        self.s.flush()
        return item
