"""Repositorios SQLAlchemy del módulo sales. La sesión es la Unit of Work."""

import uuid
from collections.abc import Collection
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.modules.sales.infrastructure.models import (
    Cliente,
    Cupon,
    ListaPrecio,
    MedioPago,
    Mesa,
    Pago,
    Precio,
    ProductoComercial,
    ProductoComercialExtra,
    ProductoOpcionGrupo,
    PromocionCupon,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import Empresa, Marca, Persona, Sucursal
from src.shared import fechas
from src.shared.models import Comprobante


class VentaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, venta_id: uuid.UUID) -> Venta | None:
        return self.s.get(Venta, venta_id)

    def get_by_idempotency(self, key: str) -> Venta | None:
        return self.s.scalar(select(Venta).where(Venta.idempotency_key == key))

    def siguiente_numero_orden(self, sucursal_id: uuid.UUID, fecha: date) -> int:
        actual = self.s.scalar(
            select(func.max(Venta.numero_orden)).where(
                Venta.sucursal_id == sucursal_id, Venta.fecha_orden == fecha
            )
        )
        return (actual or 0) + 1

    def add(self, venta: Venta) -> Venta:
        self.s.add(venta)
        self.s.flush()
        return venta

    def items(
        self, venta_id: uuid.UUID, grupo_cobro: int | None = None
    ) -> list[VentaItem]:
        q = select(VentaItem).where(VentaItem.venta_id == venta_id)
        if grupo_cobro is not None:
            q = q.where(VentaItem.grupo_cobro == grupo_cobro)
        return list(self.s.scalars(q))

    def siguiente_tanda(self, venta_id: uuid.UUID) -> int:
        """El número del próximo envío a cocina de esta venta (ADR-075).

        Empieza en 1 —el alta del pedido— y sube de a uno por cada agregado.
        Se cuenta contra las líneas vivas: si el agregado se anula entero, el
        siguiente reusa el número, y no pasa nada porque la tanda solo agrupa
        lo que está en la cola.
        """
        actual = self.s.scalar(
            select(func.max(VentaItem.tanda)).where(VentaItem.venta_id == venta_id)
        )
        return (actual or 0) + 1

    def tanda_ya_registrada(self, idempotency_key: str) -> bool:
        """¿Este envío a cocina ya entró? (RN-COM-002, ADR-075).

        Se busca en toda la tabla y no dentro de la venta: la clave es única
        global, igual que la del alta, así que un reintento mal dirigido
        tampoco puede duplicar nada.
        """
        return (
            self.s.scalar(
                select(VentaItem.id).where(
                    VentaItem.idempotency_key == idempotency_key
                )
            )
            is not None
        )

    def grupos_de_cobro(self, venta_id: uuid.UUID) -> list[int]:
        return sorted(
            set(
                self.s.scalars(
                    select(VentaItem.grupo_cobro).where(
                        VentaItem.venta_id == venta_id
                    )
                )
            )
        )

    def q_listar(
        self,
        *,
        sucursal_ids: Collection[uuid.UUID] | None,
        desde: date,
        hasta: date,
        estados: tuple[str, ...] | None = None,
        punto_venta_id: uuid.UUID | None = None,
        tipo: str | None = None,
    ):
        """Ventas de un rango de fechas, sin ejecutar: el router la pagina
        (ADR-026). Base de la pestaña de cobrados del PDV, del cierre de caja
        y del histórico de back-office.

        `sucursal_ids=None` es *sin filtro de sucursal* — solo lo usa el
        superusuario, que no tiene alcance que recortar. Una lista vacía sí
        filtra y no devuelve nada, que es lo correcto para un usuario sin
        sucursales asignadas.

        Ordena por `(fecha, número de orden)` y no solo por el número: el
        correlativo reinicia cada día en cada sucursal, así que ordenar por
        número mezclaría jornadas apenas el rango pase de un día.
        """
        q = select(Venta).where(
            Venta.fecha_orden >= desde, Venta.fecha_orden <= hasta
        )
        if sucursal_ids is not None:
            q = q.where(Venta.sucursal_id.in_(sucursal_ids))
        if estados:
            q = q.where(Venta.estado.in_(estados))
        if punto_venta_id is not None:
            q = q.where(Venta.punto_venta_id == punto_venta_id)
        # Sin filtro salen los dos tipos: el consumo de personal es parte de
        # la jornada, solo no es plata. `tipo="consumo_personal"` es la base
        # de la regularización del gasto (RN-COM-025).
        if tipo is not None:
            q = q.where(Venta.tipo == tipo)
        return q.order_by(Venta.fecha_orden, Venta.numero_orden)

    def del_dia(
        self,
        *,
        sucursal_id: uuid.UUID,
        fecha: date,
        estados: tuple[str, ...] | None = None,
        punto_venta_id: uuid.UUID | None = None,
    ) -> list[Venta]:
        return list(
            self.s.scalars(
                self.q_listar(
                    sucursal_ids=[sucursal_id],
                    desde=fecha,
                    hasta=fecha,
                    estados=estados,
                    punto_venta_id=punto_venta_id,
                )
            )
        )


class PagoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, pago_id: uuid.UUID) -> Pago | None:
        return self.s.get(Pago, pago_id)

    def get_by_idempotency(self, key: str) -> Pago | None:
        return self.s.scalar(select(Pago).where(Pago.idempotency_key == key))

    def add(self, pago: Pago) -> Pago:
        self.s.add(pago)
        self.s.flush()
        return pago

    def confirmados(
        self, venta_id: uuid.UUID, grupo_cobro: int | None = None
    ) -> list[Decimal]:
        """Sin `grupo_cobro` devuelve los pagos de toda la venta (el uso
        histórico); con él, solo los de esa cuenta."""
        q = select(Pago.monto).where(
            Pago.venta_id == venta_id, Pago.estado == "confirmado"
        )
        if grupo_cobro is not None:
            q = q.where(Pago.grupo_cobro == grupo_cobro)
        return list(self.s.scalars(q))


class ProductoComercialRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, producto_id: uuid.UUID) -> ProductoComercial | None:
        return self.s.get(ProductoComercial, producto_id)

    def get_by_id_interno(self, id_interno: str) -> ProductoComercial | None:
        return self.s.scalar(
            select(ProductoComercial).where(
                ProductoComercial.id_interno == id_interno
            )
        )

    def list(self, marca_id: uuid.UUID | None = None) -> list[ProductoComercial]:
        q = select(ProductoComercial).where(ProductoComercial.activo.is_(True))
        if marca_id is not None:
            q = q.where(ProductoComercial.marca_id == marca_id)
        return list(self.s.scalars(q.order_by(ProductoComercial.nombre)))

    def variantes_de(self, producto_id: uuid.UUID) -> "list[ProductoComercial]":
        return [
            *self.s.scalars(
                select(ProductoComercial)
                .where(
                    ProductoComercial.producto_padre_id == producto_id,
                    ProductoComercial.activo.is_(True),
                )
                .order_by(ProductoComercial.orden, ProductoComercial.nombre)
            )
        ]

    def add(self, producto: ProductoComercial) -> ProductoComercial:
        self.s.add(producto)
        self.s.flush()
        return producto

    # Anotación entre comillas a propósito: `list` está sombreado por el
    # método de arriba dentro del cuerpo de esta clase.
    def extras_de(self, producto_id: uuid.UUID) -> "list[ProductoComercialExtra]":
        return [
            *self.s.scalars(
                select(ProductoComercialExtra).where(
                    ProductoComercialExtra.producto_comercial_id == producto_id
                )
            )
        ]

    def admite_extra(
        self, producto_id: uuid.UUID, extra_id: uuid.UUID
    ) -> ProductoComercialExtra | None:
        return self.s.scalar(
            select(ProductoComercialExtra).where(
                ProductoComercialExtra.producto_comercial_id == producto_id,
                ProductoComercialExtra.extra_id == extra_id,
            )
        )

    def vincular_extra(
        self,
        producto_id: uuid.UUID,
        extra_id: uuid.UUID,
        maximo: int | None = None,
        grupo_id: uuid.UUID | None = None,
    ) -> ProductoComercialExtra:
        vinculo = ProductoComercialExtra(
            producto_comercial_id=producto_id,
            extra_id=extra_id,
            maximo=maximo,
            grupo_id=grupo_id,
        )
        self.s.add(vinculo)
        self.s.flush()
        return vinculo

    def tiene_ventas(self, producto_id: uuid.UUID) -> bool:
        return (
            self.s.scalar(
                select(VentaItem.id)
                .where(VentaItem.producto_comercial_id == producto_id)
                .limit(1)
            )
            is not None
        )

    def borrar_con_dependencias(self, producto: ProductoComercial) -> None:
        """Borra el producto y lo que solo existe por él: su precio en cada
        lista y sus vínculos de extra. Nada de eso tiene sentido sin el
        producto, y ninguna es información histórica —el precio histórico que
        importa es el de `venta_item`, que ya se cobró y no se toca."""
        for tabla, columna in (
            (Precio, Precio.producto_comercial_id),
            (ProductoComercialExtra, ProductoComercialExtra.producto_comercial_id),
            (ProductoComercialExtra, ProductoComercialExtra.extra_id),
            (ProductoOpcionGrupo, ProductoOpcionGrupo.producto_comercial_id),
        ):
            for fila in self.s.scalars(select(tabla).where(columna == producto.id)):
                self.s.delete(fila)
        self.s.flush()
        self.s.delete(producto)

    def grupos_de(self, producto_id: uuid.UUID) -> "list[ProductoOpcionGrupo]":
        return [
            *self.s.scalars(
                select(ProductoOpcionGrupo)
                .where(ProductoOpcionGrupo.producto_comercial_id == producto_id)
                .order_by(ProductoOpcionGrupo.orden, ProductoOpcionGrupo.nombre)
            )
        ]

    def get_grupo(self, grupo_id: uuid.UUID) -> ProductoOpcionGrupo | None:
        return self.s.get(ProductoOpcionGrupo, grupo_id)

    # --- Lo que ofrece de verdad un producto (ADR-042) ------------------------
    #
    # Una variante **hereda** los grupos y extras de su padre. Sin esto, dónde
    # quedó colgado el grupo decide si la carta lo muestra, y eso depende del
    # orden en que alguien armó el producto: el lienzo cuelga "+ grupo" del
    # nodo activo, que es el padre mientras el producto no tiene tamaños, así
    # que un catálogo armado a mano termina con los sabores en el padre y las
    # variantes sin nada que ofrecer.
    #
    # Los métodos crudos de arriba (`grupos_de`, `extras_de`, `admite_extra`)
    # siguen siendo por producto: los usa la ficha de catálogo, que edita lo
    # que cuelga de **este** producto y no lo que hereda.

    def grupos_efectivos(
        self, producto: ProductoComercial
    ) -> "list[ProductoOpcionGrupo]":
        """Los del producto más los de su padre. Un grupo obligatorio del
        padre lo es en todos sus tamaños: "elige un sabor" no deja de valer
        porque el cliente pidió la familiar."""
        propios = self.grupos_de(producto.id)
        if producto.producto_padre_id is None:
            return propios
        return [*self.grupos_de(producto.producto_padre_id), *propios]

    def extras_efectivos(
        self, producto: ProductoComercial
    ) -> "list[ProductoComercialExtra]":
        """Igual, y **el vínculo propio gana** sobre el heredado: si el tamaño
        familiar declara su propio "extra queso", su `maximo` y su grupo son
        más específicos que los del padre."""
        propios = self.extras_de(producto.id)
        if producto.producto_padre_id is None:
            return propios
        mios = {v.extra_id for v in propios}
        heredados = [
            v
            for v in self.extras_de(producto.producto_padre_id)
            if v.extra_id not in mios
        ]
        return [*heredados, *propios]

    def admite_extra_efectivo(
        self, producto: ProductoComercial, extra_id: uuid.UUID
    ) -> ProductoComercialExtra | None:
        """La versión de `admite_extra` que respeta la herencia. Es la que
        tiene que usar la venta: rechazar un extra que la carta ofreció es
        mandar al cajero a un error que no puede corregir."""
        propio = self.admite_extra(producto.id, extra_id)
        if propio is not None or producto.producto_padre_id is None:
            return propio
        return self.admite_extra(producto.producto_padre_id, extra_id)

    def borrar_vinculo_extra(self, vinculo: ProductoComercialExtra) -> None:
        self.s.delete(vinculo)
        self.s.flush()

    def borrar_grupo(self, grupo: ProductoOpcionGrupo) -> None:
        """Borra el grupo y suelta sus extras en vez de borrarlos: el extra
        es un producto comercial con su receta y su precio, y existe con o
        sin grupo. Quedan como extras opcionales del mismo producto."""
        for vinculo in self.s.scalars(
            select(ProductoComercialExtra).where(
                ProductoComercialExtra.grupo_id == grupo.id
            )
        ):
            vinculo.grupo_id = None
        self.s.flush()
        self.s.delete(grupo)
        self.s.flush()

    def add_grupo(self, grupo: ProductoOpcionGrupo) -> ProductoOpcionGrupo:
        self.s.add(grupo)
        self.s.flush()
        return grupo


class ClienteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, cliente_id: uuid.UUID) -> Cliente | None:
        return self.s.get(Cliente, cliente_id)

    def add(self, cliente: Cliente) -> Cliente:
        self.s.add(cliente)
        self.s.flush()
        return cliente

    def por_ruc(self, grupo_id: uuid.UUID, ruc: str) -> Cliente | None:
        """Evita duplicar el cliente corporativo al crearlo desde caja."""
        return self.s.scalar(
            select(Cliente).where(
                Cliente.grupo_id == grupo_id,
                Cliente.ruc == ruc,
                Cliente.deleted_at.is_(None),
            )
        )

    def por_persona(
        self, grupo_id: uuid.UUID, persona_id: uuid.UUID
    ) -> Cliente | None:
        """Una persona es cliente a lo más una vez por grupo: registrar dos
        veces al mismo señor partiría su historial de compras en dos."""
        return self.s.scalar(
            select(Cliente).where(
                Cliente.grupo_id == grupo_id,
                Cliente.persona_id == persona_id,
                Cliente.deleted_at.is_(None),
            )
        )


class PromocionCuponRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, promocion_id: uuid.UUID) -> PromocionCupon | None:
        return self.s.get(PromocionCupon, promocion_id)

    def activas(self, grupo_id: uuid.UUID | None = None) -> list[PromocionCupon]:
        """Las promociones activas, sin elegir por su cuenta cuál gana.

        Devuelve la lista y no la primera a propósito: hoy el negocio corre
        una campaña de cupón a la vez, y el día que haya dos, cuál aplica es
        una decisión del negocio y no un `ORDER BY` escondido acá. El caso
        de uso corta con un 409 que se lee, en vez de repartir descuentos
        contra una promoción elegida al azar.

        Sin `grupo_id` son todas: la landing pública no tiene tenant del que
        sacarlo — el cliente que escanea el QR no es usuario del ERP.
        """
        stmt = select(PromocionCupon).where(PromocionCupon.estado == "activa")
        if grupo_id is not None:
            stmt = stmt.where(PromocionCupon.grupo_id == grupo_id)
        return list(self.s.scalars(stmt.order_by(PromocionCupon.created_at)))

    def listar(self, grupo_id: uuid.UUID | None = None) -> list[PromocionCupon]:
        stmt = select(PromocionCupon)
        if grupo_id is not None:
            stmt = stmt.where(PromocionCupon.grupo_id == grupo_id)
        return list(self.s.scalars(stmt.order_by(PromocionCupon.created_at.desc())))

    def add(self, promocion: PromocionCupon) -> PromocionCupon:
        self.s.add(promocion)
        self.s.flush()
        return promocion


class CuponRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, cupon_id: uuid.UUID) -> Cupon | None:
        return self.s.get(Cupon, cupon_id)

    def por_cliente(
        self, promocion_id: uuid.UUID, cliente_id: uuid.UUID
    ) -> Cupon | None:
        return self.s.scalar(
            select(Cupon).where(
                Cupon.promocion_id == promocion_id,
                Cupon.cliente_id == cliente_id,
            )
        )

    def por_codigo(self, promocion_id: uuid.UUID, codigo: str) -> Cupon | None:
        return self.s.scalar(
            select(Cupon).where(
                Cupon.promocion_id == promocion_id,
                Cupon.codigo == codigo,
            )
        )

    def add(self, cupon: Cupon) -> Cupon:
        self.s.add(cupon)
        self.s.flush()
        return cupon


class MesaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, mesa_id: uuid.UUID) -> Mesa | None:
        return self.s.get(Mesa, mesa_id)

    def add(self, mesa: Mesa) -> Mesa:
        self.s.add(mesa)
        self.s.flush()
        return mesa

    def por_numero(self, sucursal_id: uuid.UUID, numero: int) -> Mesa | None:
        return self.s.scalar(
            select(Mesa).where(
                Mesa.sucursal_id == sucursal_id,
                Mesa.numero == numero,
            )
        )

    def de_sucursal(
        self, sucursal_id: uuid.UUID, solo_activas: bool = True
    ) -> list[Mesa]:
        q = select(Mesa).where(Mesa.sucursal_id == sucursal_id)
        if solo_activas:
            q = q.where(Mesa.activa.is_(True))
        return list(self.s.scalars(q.order_by(Mesa.numero)))

    def ocupadas(self, sucursal_id: uuid.UUID, fecha: date) -> list[Venta]:
        """Ventas de mesa que siguen en `orden` — las que el mapa del PDV
        pinta como ocupadas. Una venta pagada libera la mesa."""
        return list(
            self.s.scalars(
                select(Venta).where(
                    Venta.sucursal_id == sucursal_id,
                    Venta.fecha_orden == fecha,
                    Venta.mesa_id.is_not(None),
                    Venta.estado == "orden",
                )
            )
        )

    def orden_abierta(self, mesa_id: uuid.UUID) -> Venta | None:
        """Sin filtro de fecha, a diferencia de `ocupadas`: una orden abierta
        desde ayer también tiene que bloquear editar o retirar la mesa."""
        return self.s.scalar(
            select(Venta).where(Venta.mesa_id == mesa_id, Venta.estado == "orden")
        )

    def mesa_mayor(self, sucursal_id: uuid.UUID) -> Mesa | None:
        """La de número más alto, activa o no: es la única que se puede
        retirar sin dejar un hueco en el 1..n."""
        return self.s.scalar(
            select(Mesa)
            .where(Mesa.sucursal_id == sucursal_id)
            .order_by(Mesa.numero.desc())
            .limit(1)
        )

    def en_posicion(self, sucursal_id: uuid.UUID, x: int, y: int) -> Mesa | None:
        return self.s.scalar(
            select(Mesa).where(
                Mesa.sucursal_id == sucursal_id, Mesa.pos_x == x, Mesa.pos_y == y
            )
        )

    def posiciones_ocupadas(self, sucursal_id: uuid.UUID) -> set[tuple[int, int]]:
        filas = self.s.execute(
            select(Mesa.pos_x, Mesa.pos_y).where(Mesa.sucursal_id == sucursal_id)
        )
        return {(x, y) for x, y in filas}

    def tuvo_ventas(self, mesa_id: uuid.UUID) -> bool:
        """Cualquier venta que haya pasado por la mesa, sin importar su
        estado: decide si retirarla borra la fila o solo la desactiva."""
        return (
            self.s.scalar(select(Venta.id).where(Venta.mesa_id == mesa_id).limit(1))
            is not None
        )

    def eliminar(self, mesa: Mesa) -> None:
        self.s.delete(mesa)
        self.s.flush()


class PuntoVentaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, punto_venta_id: uuid.UUID) -> PuntoVenta | None:
        return self.s.get(PuntoVenta, punto_venta_id)

    def add(self, punto: PuntoVenta) -> PuntoVenta:
        self.s.add(punto)
        self.s.flush()
        return punto

    def de_sucursal(self, sucursal_id: uuid.UUID) -> list[PuntoVenta]:
        return list(
            self.s.scalars(
                select(PuntoVenta).where(PuntoVenta.sucursal_id == sucursal_id)
            )
        )

    def de_empresa(self, empresa_id: uuid.UUID | None = None) -> list[PuntoVenta]:
        """`empresa_id=None` = sin filtro, para el superusuario sin empresa
        asignada (`Tenant.filtro_empresa`)."""
        stmt = select(PuntoVenta).join(Sucursal, Sucursal.id == PuntoVenta.sucursal_id)
        if empresa_id is not None:
            stmt = stmt.where(Sucursal.empresa_id == empresa_id)
        return list(self.s.scalars(stmt.order_by(PuntoVenta.serie_boleta)))

    def series_en_uso(
        self, empresa_id: uuid.UUID, excluir_id: uuid.UUID | None = None
    ) -> set[str]:
        """Todas las series ocupadas por las cajas de la empresa, sin separar
        boleta de factura ni de sus notas de crédito: el correlativo es único
        por `(empresa, serie)` (RN-CPP-007/008), así que dos cajas que
        compartan cualquiera de las cuatro chocarían al emitir.

        `excluir_id` deja fuera la caja que se está editando — si no, guardar
        una caja sin tocarle la serie se rechazaría contra sí misma.
        """
        stmt = select(
            PuntoVenta.serie_boleta,
            PuntoVenta.serie_factura,
            PuntoVenta.serie_nc_boleta,
            PuntoVenta.serie_nc_factura,
        ).join(Sucursal, Sucursal.id == PuntoVenta.sucursal_id)
        stmt = stmt.where(Sucursal.empresa_id == empresa_id)
        if excluir_id is not None:
            stmt = stmt.where(PuntoVenta.id != excluir_id)
        return {serie for fila in self.s.execute(stmt) for serie in fila if serie}

    def empresa_de_sucursal(self, sucursal_id: uuid.UUID) -> uuid.UUID | None:
        return self.s.scalar(
            select(Sucursal.empresa_id).where(Sucursal.id == sucursal_id)
        )


class ComprobanteRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, comprobante_id: uuid.UUID) -> Comprobante | None:
        return self.s.get(Comprobante, comprobante_id)

    def por_venta(self, venta_id: uuid.UUID) -> Comprobante | None:
        """El primero de la venta. Con cobro dividido hay más de uno; para
        ese caso usar `por_venta_y_grupo` o `todos_de_venta`."""
        return self.s.scalar(
            select(Comprobante)
            .where(Comprobante.venta_id == venta_id)
            .order_by(Comprobante.grupo_cobro)
        )

    def por_venta_y_grupo(
        self, venta_id: uuid.UUID, grupo_cobro: int
    ) -> Comprobante | None:
        return self.s.scalar(
            select(Comprobante).where(
                Comprobante.venta_id == venta_id,
                Comprobante.grupo_cobro == grupo_cobro,
            )
        )

    def todos_de_venta(self, venta_id: uuid.UUID) -> list[Comprobante]:
        return list(
            self.s.scalars(
                select(Comprobante)
                .where(Comprobante.venta_id == venta_id)
                .order_by(Comprobante.grupo_cobro)
            )
        )

    def notas_de_credito_de(self, comprobante_id: uuid.UUID) -> list[Comprobante]:
        """Las notas que acreditan este comprobante, en orden de emisión."""
        return list(
            self.s.scalars(
                select(Comprobante)
                .where(Comprobante.afecta_comprobante_id == comprobante_id)
                .order_by(Comprobante.created_at)
            )
        )

    def cuantas_nc(self, comprobante_id: uuid.UUID) -> int:
        """Incluye las rechazadas: la clave de idempotencia cuenta intentos
        de documento, no documentos válidos."""
        return (
            self.s.scalar(
                select(func.count()).where(
                    Comprobante.afecta_comprobante_id == comprobante_id
                )
            )
            or 0
        )

    def siguiente_correlativo(self, empresa_id: uuid.UUID, serie: str) -> int:
        """El UNIQUE (empresa, serie, correlativo) corta la carrera: dos
        cajas que choquen fallan y el PDV reintenta con la misma
        idempotency_key. Serie SUNAT por punto de venta si el volumen lo pide."""
        actual = self.s.scalar(
            select(func.max(Comprobante.correlativo)).where(
                Comprobante.empresa_id == empresa_id, Comprobante.serie == serie
            )
        )
        return (actual or 0) + 1

    def pendientes(
        self, limite: int = 100, max_intentos: int | None = None
    ) -> list[Comprobante]:
        """Comprobantes que todavía se pueden emitir.

        `rechazado` queda fuera: es un veredicto de SUNAT sobre datos malos,
        no un fallo de transporte, y reintentarlo produce el mismo rechazo.
        Con `max_intentos`, también quedan fuera los que ya lo agotaron —
        reencolarlos cada ciclo solo produce el mismo `Conflicto`.
        """
        q = select(Comprobante).where(
            Comprobante.estado_emision.in_(("pendiente", "error"))
        )
        if max_intentos is not None:
            q = q.where(Comprobante.intentos_emision < max_intentos)
        return list(
            self.s.scalars(q.order_by(Comprobante.created_at).limit(limite))
        )

    def empresa(self, empresa_id: uuid.UUID) -> Empresa | None:
        return self.s.get(Empresa, empresa_id)

    def empresa_de_sucursal(self, sucursal_id: uuid.UUID) -> Empresa | None:
        sucursal = self.s.get(Sucursal, sucursal_id)
        return self.s.get(Empresa, sucursal.empresa_id) if sucursal else None

    def sucursal(self, sucursal_id: uuid.UUID | None) -> Sucursal | None:
        return self.s.get(Sucursal, sucursal_id) if sucursal_id else None

    def marca(self, marca_id: uuid.UUID | None) -> Marca | None:
        return self.s.get(Marca, marca_id) if marca_id else None

    def emitidos(
        self,
        *,
        empresa_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        tipo: str | None = None,
        estado_emision: str | None = None,
    ):
        """Los comprobantes que emitimos, del más nuevo al más viejo.

        Consulta sin `limit`: la pagina `src.shared.paginacion`. `desde`/
        `hasta` son fechas del **negocio** y se traducen a instantes UTC con
        `shared.fechas` — comparar un `created_at` UTC contra una fecha
        local corre el corte cinco horas y deja la última noche del rango
        fuera del reporte del contador.
        """
        q = select(Comprobante).where(Comprobante.direccion == "emitido")
        if empresa_id is not None:
            q = q.where(Comprobante.empresa_id == empresa_id)
        if desde is not None:
            q = q.where(Comprobante.created_at >= fechas.inicio_dia_utc(desde))
        if hasta is not None:
            q = q.where(Comprobante.created_at <= fechas.fin_dia_utc(hasta))
        if tipo is not None:
            q = q.where(Comprobante.tipo == tipo)
        if estado_emision is not None:
            q = q.where(Comprobante.estado_emision == estado_emision)
        return q.order_by(Comprobante.created_at.desc(), Comprobante.correlativo.desc())

    def cobrado_por_cuenta(
        self, venta_ids: Collection[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, int], Decimal]:
        """Cuánto se cobró en cada `(venta, grupo)`, en una sola consulta.

        El importe del comprobante se lee de los pagos confirmados de su
        cuenta y no se recalcula de las líneas: el comprobante nace cuando la
        cuenta queda pagada, así que los pagos **son** su total, y sacarlo de
        ahí evita repetir el prorrateo del descuento de la orden por cada
        fila de un listado.
        """
        if not venta_ids:
            return {}
        filas = self.s.execute(
            select(Pago.venta_id, Pago.grupo_cobro, func.sum(Pago.monto))
            .where(Pago.venta_id.in_(venta_ids), Pago.estado == "confirmado")
            .group_by(Pago.venta_id, Pago.grupo_cobro)
        )
        return {(v, g): total for v, g, total in filas}

    def persona(self, persona_id: uuid.UUID | None) -> Persona | None:
        return self.s.get(Persona, persona_id) if persona_id else None


class ListaPrecioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, lista_id: uuid.UUID) -> ListaPrecio | None:
        return self.s.get(ListaPrecio, lista_id)

    def add(self, lista: ListaPrecio) -> ListaPrecio:
        self.s.add(lista)
        self.s.flush()
        return lista

    def vigentes(
        self,
        *,
        marca_id: uuid.UUID,
        sucursal_id: uuid.UUID,
        canal: str,
        modalidad: str,
        fecha: date,
    ) -> list[ListaPrecio]:
        """Listas de la marca cuyo ámbito es compatible con la venta y que
        están vigentes a `fecha`. NULL en una dimensión = aplica a todas."""
        return list(
            self.s.scalars(
                select(ListaPrecio).where(
                    ListaPrecio.deleted_at.is_(None),
                    ListaPrecio.activa.is_(True),
                    ListaPrecio.marca_id == marca_id,
                    ListaPrecio.vigente_desde <= fecha,
                    or_(
                        ListaPrecio.vigente_hasta.is_(None),
                        ListaPrecio.vigente_hasta >= fecha,
                    ),
                    or_(
                        ListaPrecio.sucursal_id.is_(None),
                        ListaPrecio.sucursal_id == sucursal_id,
                    ),
                    or_(ListaPrecio.canal.is_(None), ListaPrecio.canal == canal),
                    or_(
                        ListaPrecio.modalidad.is_(None),
                        ListaPrecio.modalidad == modalidad,
                    ),
                )
            )
        )

    def list(self, marca_id: uuid.UUID | None = None) -> list[ListaPrecio]:
        q = select(ListaPrecio).where(ListaPrecio.deleted_at.is_(None))
        if marca_id is not None:
            q = q.where(ListaPrecio.marca_id == marca_id)
        return list(self.s.scalars(q.order_by(ListaPrecio.vigente_desde.desc())))


class PrecioRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, precio: Precio) -> Precio:
        self.s.add(precio)
        self.s.flush()
        return precio

    def por_producto(
        self, producto_id: uuid.UUID, lista_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        if not lista_ids:
            return {}
        filas = self.s.execute(
            select(Precio.lista_precio_id, Precio.monto).where(
                Precio.producto_comercial_id == producto_id,
                Precio.lista_precio_id.in_(lista_ids),
            )
        )
        return {lista_id: monto for lista_id, monto in filas}

    def de_lista(self, lista_id: uuid.UUID) -> list[Precio]:
        return list(
            self.s.scalars(select(Precio).where(Precio.lista_precio_id == lista_id))
        )


class MedioPagoRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, medio_pago_id: uuid.UUID) -> MedioPago | None:
        return self.s.get(MedioPago, medio_pago_id)

    def list(
        self,
        empresa_id: uuid.UUID | None = None,
        direccion: str | None = None,
        incluir_inactivos: bool = False,
    ) -> list[MedioPago]:
        """`direccion` incluye siempre los de `ambos`: son los mismos.

        `incluir_inactivos` es para la pantalla que los administra —tiene
        que poder reactivar lo que apagó—; quien cobra ve solo los vivos."""
        q = select(MedioPago).order_by(MedioPago.nombre)
        if not incluir_inactivos:
            q = q.where(MedioPago.activo.is_(True))
        if empresa_id is not None:
            q = q.where(MedioPago.empresa_id == empresa_id)
        if direccion is not None:
            q = q.where(MedioPago.direccion.in_((direccion, "ambos")))
        return list(self.s.scalars(q))

    def add(self, medio: MedioPago) -> MedioPago:
        self.s.add(medio)
        self.s.flush()
        return medio
