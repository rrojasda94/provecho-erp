"""DTOs (pydantic) del KDS."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.modules.sales.api.schemas import EncabezadoImpresionOut


class PantallaCreate(BaseModel):
    sucursal_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str  # preparacion | despacho
    categoria_ids: list[str] | None = None  # None/[] = todas las categorías
    # Eslabón en la cadena de preparación (ADR-044). 0 = la primera.
    orden: int = Field(default=0, ge=0)


class PantallaUpdate(BaseModel):
    # Mudar una estación de sucursal: una tablet que se lleva al local nuevo
    # no tiene por qué obligar a recrear la estación y perder su historia.
    # El router valida que la sucursal destino sea del tenant.
    sucursal_id: uuid.UUID | None = None
    nombre: str | None = None
    tipo: str | None = None
    categoria_ids: list[str] | None = None
    activo: bool | None = None
    orden: int | None = Field(default=None, ge=0)


class PantallaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sucursal_id: uuid.UUID
    nombre: str
    tipo: str
    categoria_ids: list[str] | None
    orden: int
    activo: bool


class ExtraColaOut(BaseModel):
    producto: str
    cantidad: str


class ItemColaOut(BaseModel):
    venta_item_id: str
    producto: str
    cantidad: str
    estado: str
    # Restas de la línea, ya resueltas a nombre: ["Cebolla"] → "SIN CEBOLLA"
    # en pantalla (RN-COM-028). Lista vacía = el plato va completo.
    sin: list[str] = []
    # QUÉ es el plato: las mitades de una MitadXMitad, ya resueltas a
    # "Mitad 1: Americana" (ADR-056). Distinto de `extras` —acá no hay línea
    # cobrada, la elección cambia la receta— y sin esto el pizzero que solo
    # mira la pantalla no sabe de qué mitades es la pizza.
    valores: list[str] = []
    # Lo que el plato lleva además (el sabor de la pizza, el queso extra).
    # Anidados y no como ítems propios: en cocina son el mismo plato
    # (RN-CUP-014).
    extras: list[ExtraColaOut] = []
    etapa_kds: int = 0
    # Nombre de la estación donde está la línea ahora; `None` = ya salió de
    # cocina. Es lo que despacho muestra por línea (RN-CUP-013).
    estacion: str | None = None


class PedidoColaOut(BaseModel):
    venta_id: str
    numero_orden: int
    # Qué envío del pedido es esta tarjeta (ADR-075). En preparación una
    # venta puede aparecer varias veces, una por tanda, y `venta_id` deja de
    # ser la clave de la tarjeta: lo es el par `venta_id + tanda`.
    #
    # Vale 1 en despacho y en el historial, donde la unidad sigue siendo el
    # pedido entero: la bolsa se arma completa, y "¿este pedido salió?" no se
    # responde por tandas.
    tanda: int = 1
    referencia_atencion: str | None
    # Despacho arma la bolsa mirando esta pantalla: la dirección va acá y
    # no solo en el papel. `None` salvo en delivery.
    direccion_entrega: str | None = None
    modalidad: str
    canal: str
    # `venta` | `consumo_personal` (RN-COM-025) y su motivo: la cocina
    # prioriza distinto la comida del turno que un pedido de cliente.
    tipo: str = "venta"
    consumo_motivo: str | None = None
    estado_pedido: str
    # Cuándo se tomó el pedido. El cronómetro lo corre el navegador —el
    # servidor no tiene por qué reenviar la cola entera cada segundo— y esto
    # es su punto de partida.
    creado_en: datetime
    items: list[ItemColaOut]


class SemaforoOut(BaseModel):
    """Umbrales y colores con los que la pantalla pinta el tiempo de espera.
    Son los **resueltos** —lo que Gerencia aprobó o la semilla del módulo—,
    no el contenido crudo de `parametro_empresa`."""

    minutos_ambar: int
    minutos_rojo: int
    color_normal: str
    color_ambar: str
    color_rojo: str


class PedidoHistorialOut(PedidoColaOut):
    """Un pedido ya entregado. Lo mismo que en la cola más la hora en que se
    cerró — que es lo que se lee para saber si «este» era el que salió."""

    entregado_en: datetime


class AvanzarIn(BaseModel):
    estado: str  # en_preparacion | listo | entregado


class AvanceOut(BaseModel):
    venta_id: str
    numero_orden: int
    referencia_atencion: str | None
    estado_pedido: str
    items: list[ItemColaOut]


class ComandaOut(BaseModel):
    venta_id: str
    numero_orden: int
    reimpresion: bool
    impresa_veces: int
    # Membrete de la marca: en un local multimarca todas las cocinas
    # imprimen en el mismo rollo (ADR-067).
    encabezado: EncabezadoImpresionOut
    texto: str
