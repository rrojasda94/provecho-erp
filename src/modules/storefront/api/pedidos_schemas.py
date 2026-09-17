"""Schemas del checkout público del sitio de marca (ADR-103/ADR-104)."""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.shared.ubicacion import UbicacionMixin

Modalidad = Literal["takeout", "delivery"]
MedioPago = Literal["efectivo", "izipay"]


class CotizarPedidoIn(UbicacionMixin):
    modalidad: Modalidad
    # Recojo: el cliente ya eligió el local. Delivery: se ignora, la
    # asignación automática decide (RN-WEB-010).
    sucursal_id: uuid.UUID | None = None
    ubicacion_distrito: str | None = Field(default=None, max_length=100)


class CotizacionOut(BaseModel):
    sucursal_id: uuid.UUID
    eta_min: int
    eta_max: int
    costo_delivery: Decimal | None = None
    distancia_km: Decimal | None = None


class ItemPedidoIn(BaseModel):
    producto_comercial_id: uuid.UUID
    cantidad: int = Field(gt=0, le=20)


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


class ItemPedidoOut(BaseModel):
    nombre_congelado: str
    cantidad: int
    precio_unitario_congelado: Decimal


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
    # Solo va en la respuesta de confirmación: es la credencial para que un
    # invitado sin cuenta vuelva a consultar su pedido.
    token_acceso: str | None = None
    items: list[ItemPedidoOut] = []
