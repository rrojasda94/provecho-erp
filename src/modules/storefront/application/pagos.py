"""Resultado del pago de un pedido web con Izipay (ADR-105).

La pasarela avisa por webhook si el cobro se aprobó o se rechazó. Recién ahí
el pedido se convierte en venta (aprobado) o se cierra como fallido
(rechazado): un pedido sin pagar nunca llega a cocina.
"""

from sqlalchemy.orm import Session

from src.modules.storefront.application import pedidos
from src.modules.storefront.application.errors import NoEncontrado
from src.modules.storefront.infrastructure.repositories import PedidoRepo
from src.shared import auditoria


def registrar_resultado(session: Session, *, id_externo: str, aprobado: bool) -> None:
    """Idempotente: la pasarela reintenta el webhook hasta que se le contesta,
    y un segundo aviso del mismo pago no puede crear otra venta."""
    pedido = PedidoRepo(session).get_by_pago_externo(id_externo)
    if pedido is None:
        raise NoEncontrado("pago desconocido")
    if pedido.pago_estado != "pendiente":
        return

    if aprobado:
        pedido.pago_estado = "aprobado"
        pedidos.publicar_confirmacion(session, pedido)
    else:
        pedido.pago_estado = "rechazado"
        pedido.estado = "fallido"
        pedido.fallo_motivo = "El pago fue rechazado."
    auditoria.registrar(
        session,
        usuario_id=None,
        entidad="storefront_pedido",
        entidad_id=pedido.id,
        accion="pago_aprobado" if aprobado else "pago_rechazado",
        datos_despues={"pago_id_externo": id_externo},
    )
    session.commit()
