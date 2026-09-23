"""Pedido del sitio de marca (checkout, ADR-105): lo que el cliente confirmó
en `charlies.majambo.com.pe`, antes y después de que `sales` lo convierta en
una `Venta` real.

`storefront` es dueño de este registro porque es lo único que el sitio
necesita para mostrarle al cliente "tu pedido fue recibido" / "algo salió
mal" sin depender de una respuesta síncrona de `sales` — el bus de eventos
es síncrono en proceso (`core/events.py`), así que en la práctica la fila
ya sale `confirmado` o `fallido` en la misma request, pero el diseño no
depende de esa latencia.

`venta_id`/`numero_orden` quedan NULL mientras `estado='pendiente'` y se
completan cuando `sales` responde con `sales.pedido_web_procesado`
(`application/listeners.py::on_pedido_web_procesado`).
"""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UbicacionMixin, UuidPkMixin


class StorefrontPedido(Base, UuidPkMixin, TimestampMixin, UbicacionMixin):
    __tablename__ = "storefront_pedido"

    __table_args__ = (
        CheckConstraint(
            "modalidad IN ('takeout', 'delivery')", name="modalidad_storefront_pedido"
        ),
        CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'fallido')",
            name="estado_storefront_pedido",
        ),
        CheckConstraint(
            "medio_pago IN ('efectivo', 'izipay')", name="medio_pago_storefront_pedido"
        ),
    )

    marca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("marca.id"))
    # NULL = compró como invitado (RN-WEB-012): el checkout nunca exige cuenta.
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("storefront_cuenta.id"), nullable=True, index=True
    )
    nombre_contacto: Mapped[str] = mapped_column(String(150))
    telefono_contacto: Mapped[str] = mapped_column(String(20))
    email_contacto: Mapped[str | None] = mapped_column(String(255), nullable=True)

    modalidad: Mapped[str] = mapped_column(
        String(10)
    )  # 'takeout' | 'delivery' — sin Enum nativo, mismo criterio que otras tablas
    # NULL solo mientras `estado='pendiente'` y la asignación automática (o
    # el recojo elegido por el cliente) todavía no se resolvió.
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # Congelada al confirmar (mismo criterio que `venta.direccion_entrega`):
    # solo delivery. `ubicacion_*` del mixin trae el destino para cotizar.
    direccion_entrega: Mapped[str | None] = mapped_column(String(255), nullable=True)

    medio_pago: Mapped[str] = mapped_column(String(10))  # 'efectivo' | 'izipay'
    # Solo con Izipay (NULL en efectivo): `pendiente` hasta que la pasarela
    # avisa por webhook, luego `aprobado` | `rechazado`. La venta se crea
    # recién al aprobarse — un pedido sin pagar no debe llegar a cocina.
    pago_estado: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Id del intento en la pasarela: único, es lo que hace idempotente el
    # webhook (la pasarela reintenta hasta que se le contesta).
    pago_id_externo: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    # Lo que el cliente tecleó para su comprobante — DNI (boleta) o RUC
    # (factura, 11 dígitos, `rules.tipo_comprobante_por_documento`). Igual
    # que el resto del ERP, decide el tipo el largo del documento.
    numero_documento: Mapped[str | None] = mapped_column(String(15), nullable=True)
    nombre_o_razon_social: Mapped[str | None] = mapped_column(String(150), nullable=True)

    total_estimado: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    costo_delivery_estimado: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    distancia_km_estimada: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    eta_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    estado: Mapped[str] = mapped_column(String(12), default="pendiente")
    fallo_motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venta.id"), nullable=True, unique=True
    )
    numero_orden: Mapped[int | None] = mapped_column(Integer, nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # Deja que un invitado (sin cuenta, sin JWT) consulte su propio pedido
    # por `GET /storefront/publico/pedidos/{id}?token=...` — mismo patrón
    # que `convocatoria.token_publico` y el seguimiento de `delivery`.
    token_acceso: Mapped[str] = mapped_column(String(64), unique=True)
