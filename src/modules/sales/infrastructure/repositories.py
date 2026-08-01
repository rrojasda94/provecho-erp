"""Repositorios SQLAlchemy del módulo sales. La sesión es la Unit of Work."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.modules.sales.infrastructure.models import (
    Cliente,
    ListaPrecio,
    MedioPago,
    Mesa,
    Pago,
    Precio,
    ProductoComercial,
    ProductoComercialExtra,
    PuntoVenta,
    Venta,
    VentaItem,
)
from src.modules.users.infrastructure.models import Empresa, Persona, Sucursal
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

    def del_dia(
        self,
        *,
        sucursal_id: uuid.UUID,
        fecha: date,
        estados: tuple[str, ...] | None = None,
        punto_venta_id: uuid.UUID | None = None,
    ) -> list[Venta]:
        """Ventas de una jornada. Base de la pestaña de cobrados del PDV y
        del cierre de caja: sin esto el cajero no puede verificar lo vendido
        ni reenviar un comprobante que el cliente perdió."""
        q = select(Venta).where(
            Venta.sucursal_id == sucursal_id, Venta.fecha_orden == fecha
        )
        if estados:
            q = q.where(Venta.estado.in_(estados))
        if punto_venta_id is not None:
            q = q.where(Venta.punto_venta_id == punto_venta_id)
        return list(self.s.scalars(q.order_by(Venta.numero_orden)))


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
        self, producto_id: uuid.UUID, extra_id: uuid.UUID, maximo: int | None = None
    ) -> ProductoComercialExtra:
        vinculo = ProductoComercialExtra(
            producto_comercial_id=producto_id, extra_id=extra_id, maximo=maximo
        )
        self.s.add(vinculo)
        self.s.flush()
        return vinculo


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
                Mesa.deleted_at.is_(None),
            )
        )

    def de_sucursal(
        self, sucursal_id: uuid.UUID, solo_activas: bool = True
    ) -> list[Mesa]:
        q = select(Mesa).where(
            Mesa.sucursal_id == sucursal_id, Mesa.deleted_at.is_(None)
        )
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


class PuntoVentaRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, punto_venta_id: uuid.UUID) -> PuntoVenta | None:
        return self.s.get(PuntoVenta, punto_venta_id)


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

    def pendientes(self, limite: int = 100) -> list[Comprobante]:
        return list(
            self.s.scalars(
                select(Comprobante)
                .where(Comprobante.estado_emision.in_(("pendiente", "error")))
                .order_by(Comprobante.created_at)
                .limit(limite)
            )
        )

    def empresa(self, empresa_id: uuid.UUID) -> Empresa | None:
        return self.s.get(Empresa, empresa_id)

    def empresa_de_sucursal(self, sucursal_id: uuid.UUID) -> Empresa | None:
        sucursal = self.s.get(Sucursal, sucursal_id)
        return self.s.get(Empresa, sucursal.empresa_id) if sucursal else None

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

    def list(self, empresa_id: uuid.UUID | None = None) -> list[MedioPago]:
        q = select(MedioPago).where(MedioPago.activo.is_(True))
        if empresa_id is not None:
            q = q.where(MedioPago.empresa_id == empresa_id)
        return list(self.s.scalars(q))

    def add(self, medio: MedioPago) -> MedioPago:
        self.s.add(medio)
        self.s.flush()
        return medio
