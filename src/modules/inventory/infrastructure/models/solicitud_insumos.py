"""solicitud_insumos: lo que un almacén le pide a su abastecedor.

Va por **almacén** y no por sucursal (como decía el borrador del modelo):
el almacén de producción también solicita, y la transferencia que sale de
acá opera sobre almacenes. La sucursal se deriva de `almacen.sucursal_id`.

Caso concreto del concepto marco Solicitud (RN-DOC-005).
"""

import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import TimestampMixin, UuidPkMixin

ESTADO_SOLICITUD = Enum(
    # La lista que el turno va juntando durante la jornada (RN-INV-023).
    # Todavía no le pidió nada a nadie, así que no aparece en el listado de
    # solicitudes ni reserva stock: enviarla es lo que la vuelve un pedido.
    "borrador",
    "pendiente",
    "aprobada",
    "rechazada",
    "cancelada",
    "despachada",
    "recibida",
    name="estado_solicitud",
    native_enum=False,
)


class SolicitudInsumos(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "solicitud_insumos"

    almacen_solicitante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("almacen.id")
    )
    # Quién debe surtirla. Se resuelve del `almacen_abastecedor_id` del
    # solicitante; explícito en la fila para que cambiar el abastecedor de
    # un almacén no reescriba la historia de lo ya pedido.
    almacen_abastecedor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("almacen.id")
    )
    estado: Mapped[str] = mapped_column(ESTADO_SOLICITUD, default="pendiente")
    solicitado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    aprobado_por: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
