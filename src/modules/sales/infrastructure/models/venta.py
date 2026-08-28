"""Venta: alcance corregido 2026-07-14 (RN-COM-005) — termina en el envío
del pedido a cocina y el cobro. Preparación/entrega pertenecen al futuro
proceso "cumplimiento de pedido", aún sin definir.

Toda venta confirmada ya ES una Orden de Pedido (glosario), tenga o no
`cotizacion_id` — `numero_orden` es el correlativo legible por sucursal y
día que ve el personal (cocina/mostrador/KDS); `idempotency_key` es
técnico (anti-duplicado), no se muestra a nadie. La generación del
correlativo (siguiente número del día para esa sucursal) es lógica de
aplicación, aún no construida — el esquema solo declara la unicidad.

Medio de pago, pago, comprobante y demás entidades de PROC-COM-002 (Cobro)
se modelan en un slice posterior de este mismo proceso Venta.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, column_property, declared_attr, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UbicacionMixin, UuidPkMixin
from src.modules.sales.infrastructure.models.mesa import Mesa


class Venta(Base, UuidPkMixin, TimestampMixin, UbicacionMixin):
    __tablename__ = "venta"
    __table_args__ = (UniqueConstraint("sucursal_id", "fecha_orden", "numero_orden"),)

    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    # Día de negocio de la orden (lo fija la aplicación al crear) — base
    # estable para el correlativo, independiente de la hora exacta de
    # created_at.
    fecha_orden: Mapped[date] = mapped_column(default=date.today)
    numero_orden: Mapped[int] = mapped_column(Integer)
    punto_venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("punto_venta.id"))
    canal: Mapped[str] = mapped_column(
        Enum("pdv", "agente_ia", "delivery", name="canal_venta", native_enum=False)
    )
    modalidad: Mapped[str] = mapped_column(
        Enum("mesa", "takeout", "delivery", name="modalidad_venta", native_enum=False)
    )
    # Opcional — venta de servicio o del área comercial originada en
    # cotización aceptada por el cliente (RN-COM-004). Entidad `cotizacion`
    # se modela en el slice de Compras/Comercial que la comparte.
    cotizacion_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cliente.id"), nullable=True
    )
    # Cajero o agente_ia — quien atendió; base del ranking de venta por
    # trabajador (join usuario_id -> trabajador.usuario_id).
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # `cerrada` es el estado terminal de lo que se preparó y entregó sin
    # cobrarse: hoy solo el consumo de personal (RN-COM-025). Sin él una
    # orden sin precio quedaría `orden` para siempre, contada como cuenta
    # abierta en el PDV y en el cierre de caja.
    estado: Mapped[str] = mapped_column(
        Enum(
            "orden",
            "pagada",
            "facturada",
            "anulada",
            "cerrada",
            name="estado_venta",
            native_enum=False,
        ),
        default="orden",
    )
    # --- Consumo de personal (RN-COM-025) ------------------------------------
    tipo: Mapped[str] = mapped_column(
        Enum("venta", "consumo_personal", name="tipo_venta", native_enum=False),
        default="venta",
    )
    # Por qué se alimentó al personal ese día. Enum cerrado a propósito: el
    # dato existe para agrupar el gasto por causa, y un texto libre no agrupa.
    consumo_motivo: Mapped[str | None] = mapped_column(
        Enum(
            "fin_semana",
            "feriado",
            "alta_actividad",
            "capacitacion",
            "otro",
            name="motivo_consumo_personal",
            native_enum=False,
        ),
        nullable=True,
    )
    # Encargado que lo autorizó con su PIN — nunca el mismo que lo registra.
    consumo_autorizado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    # `rappi` | `ubereats` | `pedidosya` | ... si un rider de plataforma
    # externa hizo el delivery (RN-PER-003).
    repartidor_externo_plataforma: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    # Contador de impresiones de comanda (>1 = reimpresión, auditable).
    comanda_impresa_veces: Mapped[int] = mapped_column(Integer, default=0)
    # Para quién es el pedido, como lo canta el mesero: "Carlos",
    # "Rappi #1042". Texto libre — no exige cliente registrado. Visible en
    # KDS y comanda para aclarar problemas en cocina. Para `modalidad=mesa`
    # el dato tipado es `mesa_id`; este campo queda para takeout/delivery.
    referencia_atencion: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    # Adónde va el pedido de delivery, congelada al tomarlo: si el cliente se
    # muda el mes que viene, este pedido siguió yendo adonde fue. Mismo
    # criterio que las direcciones congeladas de la guía de remisión.
    #
    # Hasta 2026-08-22 se tecleaba en caja y se perdía: vivía solo en el
    # borrador del navegador y ninguna columna la recibía.
    direccion_entrega: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Lo cotizado al crear la orden, no lo que daría recalcular hoy: la
    # tarifa cambia y el pedido de ayer no puede cambiar de precio (ADR-054).
    distancia_entrega_km: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    costo_entrega: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    # Solo si modalidad=mesa (validado en el dominio, no en el esquema).
    # Nullable también por compatibilidad: las ventas anteriores a la
    # entidad `mesa` solo tienen `referencia_atencion`.
    mesa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mesa.id"), nullable=True
    )

    # Derivado, no columna: el número que ve el personal ("Mesa 7").
    #
    # Existe porque el PDV reabre una cuenta desde la pestaña de cuentas
    # abiertas, y por ese camino nunca pasó por el mapa de salón: se quedaba
    # con el `mesa_id` y la pestaña decía "Mesa ?". El número es de la mesa,
    # no de la venta, así que duplicarlo en una columna sería una segunda
    # fuente de verdad para un dato que además es inmutable (RN-MDC-004).
    #
    # Subconsulta y no `relationship`: `GET /sales/ventas` está paginado y un
    # eager load por fila —o peor, un lazy load por fila— es exactamente lo
    # que no puede pagar la pantalla que se refresca en cada cobro.
    @declared_attr
    def mesa_numero(cls) -> Mapped[int | None]:
        return column_property(
            select(Mesa.numero)
            .where(Mesa.id == cls.mesa_id)
            .correlate_except(Mesa)
            .scalar_subquery()
        )

    # Cuántos comen en la mesa. Opcional: el cajero no siempre lo pregunta.
    # Base del ticket promedio por comensal.
    comensales: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # --- Descuento manual de la orden (RN-COM-017) ---------------------------
    # Distinto de `venta_item.descuento` (monto por línea que sale de listas
    # promocionales) y de las promociones condicionales por marca/sucursal,
    # que son un motor aparte aún no construido. Este es el descuento que el
    # cajero aplica al total y un supervisor autoriza; se guarda con motivo y
    # autor para que salga en los reportes.
    descuento_modo: Mapped[str | None] = mapped_column(
        Enum("porcentaje", "monto", name="modo_descuento_venta", native_enum=False),
        nullable=True,
    )
    descuento_valor: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    descuento_motivo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Quién lo autorizó con su PIN — nunca es el mismo acto que aplicarlo.
    descuento_autorizado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
