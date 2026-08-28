"""Promoción condicional: la que se activa sola cuando el pedido cumple
(ADR-076).

No confundir con `promocion_cupon` (ADR-061), que emite un código por cliente
y se canjea a mano. Acá no hay nada que canjear: el cajero no la pide ni la
firma, el pedido la cumple o no.

Tampoco con `venta.descuento_*`, que es el descuento manual de un supervisor.
Esa frontera es el motivo por el que existe `venta_promocion` en vez de
reusar esas columnas: sin ella, el reporte de descuentos no podría distinguir
lo que regaló una persona de lo que aplicó una regla.
"""

import uuid
from datetime import date, time

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, SoftDeleteMixin, TimestampMixin, UuidPkMixin


class Promocion(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "promocion"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    # Se apaga sin borrarla: una promoción que corrió tiene ventas colgando y
    # el reporte necesita poder nombrarla (RN-PRM-005).
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Vigencia -------------------------------------------------------------
    # Todo nullable = "siempre". Una promoción sin fechas corre hasta que
    # alguien la apague, que es como se piden la mitad de ellas.
    desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Días de la semana en los que corre, `0` = lunes (`date.weekday()`).
    # NULL o vacío = todos. Es lo que expresa "los martes de pizzas".
    dias_semana: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Franja horaria. Admite cruzar la medianoche (22:00–02:00): el happy
    # hour de madrugada es un caso real.
    hora_desde: Mapped[time | None] = mapped_column(Time, nullable=True)
    hora_hasta: Mapped[time | None] = mapped_column(Time, nullable=True)

    # --- Ámbito ---------------------------------------------------------------
    # NULL = toda la empresa. Una promoción de una marca no puede activarse en
    # el local de la otra, y una de un local no puede activarse en el resto.
    marca_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marca.id"), nullable=True
    )
    sucursal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sucursal.id"), nullable=True
    )
    # `["pdv"]`, `["mesa", "takeout"]`. NULL o vacío = todos. Existe porque
    # una promoción de salón no siempre vale en delivery, donde el margen ya
    # se lo comió el reparto.
    canales: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    modalidades: Mapped[list | None] = mapped_column(JsonB, nullable=True)

    # --- Resolución de solapes ------------------------------------------------
    # Quién toma las unidades primero cuando dos promociones alcanzan el mismo
    # plato. Mayor gana.
    prioridad: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # `True` = se suma a lo que otras ya aplicaron sobre las mismas unidades.
    # El default es `False` porque acumular es lo que hace que el local
    # regale más de lo que aprobó, y eso tiene que ser una decisión explícita.
    acumulable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )

    # --- Qué hace -------------------------------------------------------------
    tipo: Mapped[str] = mapped_column(
        Enum(
            "nxm",
            "cantidad",
            "combo",
            "monto_minimo",
            name="tipo_promocion",
            native_enum=False,
        )
    )
    # La condición y el beneficio, con la forma que le toca a cada `tipo`
    # (validadas por Pydantic en la API, documentadas en ADR-076).
    #
    # JSONB y no cuatro tablas: los cuatro tipos comparten vigencia, ámbito y
    # resolución de solapes —que es casi toda la entidad— y difieren en dos o
    # tres números. Cuatro tablas serían cuatro veces la misma fila con una
    # columna distinta, cuatro migraciones cada vez que aparezca un tipo, y un
    # `UNION` para listarlas. Mismo criterio que `sin_articulo_ids`: un objeto
    # que solo se lee entero, junto con su fila.
    condicion: Mapped[dict] = mapped_column(JsonB, nullable=False)
    beneficio: Mapped[dict] = mapped_column(JsonB, nullable=False)


class VentaPromocion(Base, UuidPkMixin, TimestampMixin):
    """Una promoción aplicada a una venta, con lo que descontó.

    Tabla propia y no columnas en `venta`: un pedido puede activar más de
    una, y aplanarlas obligaría a elegir cuál se guarda.

    Se recalcula entera en cada cambio del pedido (`recalcular_promociones`),
    así que no lleva rastro de quién la aplicó: no la aplicó nadie.
    """

    __tablename__ = "venta_promocion"

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta.id"), index=True)
    promocion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("promocion.id"))
    # El nombre congelado al aplicarse. La promoción se renombra o se apaga, y
    # el ticket de ayer tiene que seguir diciendo lo que el cliente leyó.
    nombre: Mapped[str] = mapped_column(String(120))
    monto: Mapped[float] = mapped_column(Numeric(10, 2))
    # Qué unidades de qué líneas la activaron: `{venta_item_id: unidades}`.
    # Es lo que permite explicarle al cliente por qué su pizza salió gratis y
    # la del otro no.
    detalle: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
