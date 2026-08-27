"""Mesa: puesto físico del salón de una sucursal (RN-MDC-001).

Vive en `sales` y no en `users` aunque sea mobiliario de la sucursal: quien
la usa y le da sentido es la toma de pedido (`venta.mesa_id`), y el módulo
dueño de la venta no puede importar el dominio de otro (CLAUDE.md). De
`users` solo se referencia `sucursal_id`, igual que hace `punto_venta`.

Reemplaza el uso de `venta.referencia_atencion` para el caso mesa: ese
campo sigue existiendo como texto libre para takeout/delivery ("Carlos",
"Rappi #1042"), pero el número de mesa ahora es un dato tipado y
consultable (mapa de mesas ocupadas, ventas por mesa).

Sin `SoftDeleteMixin` a propósito: una mesa se retira de verdad si nunca
tuvo ventas, o queda `activa=False` si las tuvo — nunca las dos cosas a la
vez. Un `deleted_at` que nadie escribe es una segunda fuente de verdad que
se desincroniza de `activa` el primer día que alguien la consulte.

El número lo asigna el sistema (RN-MDC-004): el salón se numera 1..n sin
huecos, así que "Mesa 3" significa siempre la misma mesa en el historial de
ventas. Por eso `numero` no es editable — la única forma de tocarlo es
crear (siguiente disponible) o retirar (siempre la de número más alto).

`pos_x`/`pos_y` ubican la mesa en el plano del salón: son la celda de una
grilla de `rules.MESA_COLUMNAS` columnas, no un píxel. Alcanza para
arrastrar mesas en un croquis sin cargar con rotación, forma ni zoom — eso
se revisa si alguna vez hace falta.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin


class Mesa(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "mesa"
    # Los dos nombres van a mano: la convención de `NAMING_CONVENTION` arma
    # el `uq` con tabla + PRIMERA columna, y los dos únicos empiezan por
    # `sucursal_id` — sin nombrarlos, Postgres rechazaría el segundo al
    # crear la tabla (mismo caso que `cupon.py`).
    __table_args__ = (
        UniqueConstraint("sucursal_id", "numero", name="uq_mesa_sucursal_numero"),
        UniqueConstraint(
            "sucursal_id", "pos_x", "pos_y", name="uq_mesa_sucursal_posicion"
        ),
    )

    # El mapa del salón se consulta por sucursal en cada refresco del PDV.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sucursal.id"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    # "Salón", "Terraza", "Barra" — agrupa el mapa de mesas. Libre porque
    # cada local nombra sus zonas distinto.
    zona: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Comensales que caben; referencia para el anfitrión, no un tope duro.
    capacidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Celda del plano (columna, fila), base 0. Únicas por sucursal: dos
    # mesas no se pueden arrastrar a la misma celda.
    pos_x: Mapped[int] = mapped_column(Integer, default=0)
    pos_y: Mapped[int] = mapped_column(Integer, default=0)
    # Baja lógica sin borrar historia: una mesa retirada del salón deja de
    # ofrecerse en el PDV pero sus ventas pasadas siguen resolviendo. Solo
    # se usa cuando la mesa ya tuvo ventas — si nunca las tuvo, se borra de
    # verdad (application/mesas.py:eliminar_mesa).
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
