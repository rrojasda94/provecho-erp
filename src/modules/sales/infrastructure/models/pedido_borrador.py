"""Pedido borrador: el ticket a medio armar de una caja, guardado del lado
del servidor (ADR-074).

Hasta ahora el borrador vivía **solo** en la memoria del navegador: recargar
la página, quedarse sin batería o cambiar de turno borraba las pestañas de
pedido y el mesero tenía que volver a teclear la mesa entera.

Es del **punto de venta**, no del usuario que lo armó: el relevo de turno
tiene que poder seguir el pedido que dejó el anterior sin que este cierre
sesión primero. Quién lo tocó por última vez queda en `usuario_id`.

No es una `venta` en estado `borrador` a propósito. Una venta consume
`numero_orden` —el correlativo legible por sucursal y día—, y numerar algo
que quizá nunca salga de la caja deja huecos en la serie que el personal lee
como pedidos perdidos. Además obligaría a filtrar ese estado en todas las
consultas que hoy asumen que una `venta` es una venta.
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class PedidoBorrador(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "pedido_borrador"

    # El id lo pone el PDV: es el mismo uuid que la pestaña ya tenía en el
    # navegador, así que guardar es un upsert y no hace falta un viaje previo
    # para saber qué id le tocó.
    sucursal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sucursal.id"))
    punto_venta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("punto_venta.id"), index=True
    )
    # Quién lo tocó por última vez. No restringe quién lo puede seguir: el
    # borrador es de la caja.
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    # El borrador entero como lo entiende el PDV: tipo de orden, mesa,
    # comensales, cliente y líneas con sus extras, restas y atributos.
    #
    # JSONB y no columnas: un borrador **no es un hecho de negocio** hasta que
    # se envía —no descuenta stock, no asienta, no se cobra— y modelarlo en
    # columnas obligaría a una migración cada vez que el ticket del PDV gane
    # un campo. El día que haya que reportar sobre borradores (¿qué se arma y
    # no se cobra?), esto se normaliza; hoy sería una tabla llena de columnas
    # que solo se leen juntas y de una sola vez.
    contenido: Mapped[dict] = mapped_column(JsonB, nullable=False)
