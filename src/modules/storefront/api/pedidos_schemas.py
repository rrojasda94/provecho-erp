"""Schemas del checkout público del sitio de marca (ADR-105)."""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.shared.ubicacion import UbicacionMixin

Modalidad = Literal["takeout", "delivery"]
MedioPago = Literal["efectivo", "izipay"]


class ExtraPedidoIn(BaseModel):
    producto_comercial_id: uuid.UUID
    # Por unidad del producto: 2 pizzas con "extra queso" x1 son 2 porciones.
    cantidad: int = Field(gt=0, le=3)


class ItemPedidoIn(BaseModel):
    producto_comercial_id: uuid.UUID
    cantidad: int = Field(gt=0, le=20)
    extras: list[ExtraPedidoIn] = Field(default=[], max_length=10)
    # `producto_atributo_valor.id` (los sabores de la Mitad x Mitad).
    valores_variante_ids: list[uuid.UUID] = Field(default=[], max_length=6)


class CotizarPedidoIn(UbicacionMixin):
    modalidad: Modalidad
    # Recojo: el cliente ya eligió el local. Delivery: se ignora, la
    # asignación automática decide (RN-WEB-010).
    sucursal_id: uuid.UUID | None = None
    ubicacion_distrito: str | None = Field(default=None, max_length=100)
    # Lo que hay en el carrito: el estimado de espera depende de qué se pide
    # (una botella de agua no tarda lo que seis pizzas, RN-WEB-011).
    items: list[ItemPedidoIn] = Field(default=[], max_length=30)


class CotizacionOut(BaseModel):
    sucursal_id: uuid.UUID
    eta_min: int
    eta_max: int
    costo_delivery: Decimal | None = None
    distancia_km: Decimal | None = None


class ConfirmarPedidoIn(UbicacionMixin):
    modalidad: Modalidad
    sucursal_id: uuid.UUID | None = None
    items: list[ItemPedidoIn] = Field(min_length=1, max_length=30)
    nombre_contacto: str = Field(min_length=2, max_length=150)
    telefono_contacto: str = Field(min_length=6, max_length=20)
    email_contacto: str | None = Field(default=None, max_length=255)
    direccion_entrega: str | None = Field(default=None, max_length=255)
    ubicacion_distrito: str | None = Field(default=None, max_length=100)
    medio_pago: MedioPago
    # DNI (boleta) o RUC de 11 dígitos (factura) — decide el tipo el largo,
    # mismo criterio que el resto del ERP (RN-CPP-003).
    numero_documento: str | None = Field(default=None, max_length=15)
    nombre_o_razon_social: str | None = Field(default=None, max_length=150)
    idempotency_key: str = Field(min_length=8, max_length=100)


class ExtraPedidoOut(BaseModel):
    nombre: str
    cantidad: int
    precio: Decimal


class ItemPedidoOut(BaseModel):
    nombre_congelado: str
    cantidad: int
    precio_unitario_congelado: Decimal
    extras: list[ExtraPedidoOut] = []
    # Nombres de los sabores/valores elegidos, para mostrar.
    valores: list[str] = []


class PedidoOut(BaseModel):
    id: uuid.UUID
    estado: Literal["pendiente", "confirmado", "fallido"]
    numero_orden: int | None
    fallo_motivo: str | None
    modalidad: Modalidad
    sucursal_id: uuid.UUID | None
    medio_pago: MedioPago
    total_estimado: Decimal
    costo_delivery_estimado: Decimal | None
    eta_min: int | None
    eta_max: int | None
    # Solo con Izipay (`None` en efectivo).
    pago_estado: Literal["pendiente", "aprobado", "rechazado"] | None = None
    # Pasarela de prueba (sin `IZIPAY_API_KEY`): la pantalla de pago ofrece
    # aprobar/rechazar a mano y necesita el id del intento para hacerlo.
    pago_simulado: bool = False
    pago_id_externo: str | None = None
    # Solo va en la respuesta de confirmación: es la credencial para que un
    # invitado sin cuenta vuelva a consultar su pedido.
    token_acceso: str | None = None
    items: list[ItemPedidoOut] = []
