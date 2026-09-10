"""Listeners de `users`: un reporte emitido se convierte en bandeja.

Antes había un handler por hecho (pedido demorado, stock bajo mínimo, lote
vencido, conteo vencido), cada uno con su título, su nivel y su regla de
destinatarios cableados. Eran cuatro copias de la misma mecánica y agregar un
aviso era escribir la quinta.

Ahora hay **uno solo**. `reports` decide qué se reporta y a quién (contra
reglas administrables, ADR-033) y publica `reports.reporte_emitido` con la
lista ya resuelta; acá solo se llena la campana. `users` sigue siendo dueño
del destinatario y de su bandeja — por eso el salto extra existe: `reports`
nunca importa `notificacion`.

El handler abre **su propia sesión**: el bus despacha después del commit del
emisor (`core/events.py`), así que la transacción que originó el hecho ya
cerró. Un fallo acá no puede deshacerla, y por eso tampoco se propaga.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.users.application import notificaciones
from src.modules.users.infrastructure.models import Usuario
from src.shared.integrations.email import smtp

log = logging.getLogger("provecho.app")

# Inyectable (los tests la reemplazan, ver `MODULOS_CON_SESSION_FACTORY` en
# `tests/conftest.py`). `reports.reporte_emitido` se dispara desde muchas
# operaciones, así que sin esto cualquier test que confirme una venta
# despertaría este listener contra el Postgres real.
session_factory = SessionLocal

_registrado = False


def _enviar_por_correo(
    session: Session, destinatarios: list[uuid.UUID], *, titulo: str, cuerpo: str | None
) -> None:
    """Además de la bandeja: si la regla eligió canal `email`, manda el
    correo a quien tenga uno registrado. Un destinatario sin `email` o un
    SMTP caído no bloquean a los demás — cada envío se intenta y se loguea
    por separado, mismo criterio que el resto de esta bandeja (un fallo acá
    nunca puede deshacer el hecho que lo originó)."""
    if not smtp.configurado():
        return
    correos = dict(
        session.execute(
            select(Usuario.id, Usuario.email).where(
                Usuario.id.in_(destinatarios), Usuario.email.is_not(None)
            )
        ).all()
    )
    for usuario_id, correo in correos.items():
        try:
            smtp.enviar(destinatario=correo, asunto=titulo, cuerpo=cuerpo or titulo)
        except Exception:
            log.exception(
                "Falló el envío por correo de un reporte", extra={"usuario_id": str(usuario_id)}
            )


def on_reporte_emitido(payload: dict) -> None:
    """Un reporte ya emitido y con destinatarios resueltos → una fila de
    bandeja por persona, y un correo más si la regla eligió ese canal.

    La notificación apunta al **reporte**, no al hecho original
    (`referencia_tipo="reporte_emitido"`): el reporte ya guarda la referencia
    al hecho junto con su foto de datos, así que apuntar ahí es apuntar a
    todo. `tipo` sigue siendo el código de la emisión, que es lo que el
    frontend usa para agrupar e iconizar.

    La bandeja se llena **siempre**, sin importar el canal: es el registro
    en el ERP de que el hecho se reportó, y el único lugar donde alguien
    marca "leído" (`notificacion.leida_at`) — el correo es un aviso, no un
    reemplazo de la bandeja.
    """
    destinatarios = [uuid.UUID(u) for u in payload.get("destinatarios") or []]
    if not destinatarios:
        return
    sucursal_id = payload.get("sucursal_id")
    try:
        with session_factory() as session:
            notificaciones.notificar(
                session,
                destinatarios,
                tipo=payload["codigo"],
                nivel=payload.get("nivel", "aviso"),
                titulo=payload["titulo"],
                cuerpo=payload.get("cuerpo"),
                referencia_tipo="reporte_emitido",
                referencia_id=uuid.UUID(payload["reporte_emitido_id"]),
                sucursal_id=uuid.UUID(sucursal_id) if sucursal_id else None,
            )
            if payload.get("canal") == "email":
                _enviar_por_correo(
                    session, destinatarios, titulo=payload["titulo"], cuerpo=payload.get("cuerpo")
                )
            session.commit()
    except Exception:
        log.exception(
            "Falló el llenado de bandeja de un reporte",
            extra={"reporte_emitido_id": payload.get("reporte_emitido_id")},
        )


def register() -> None:
    """Idempotente: create_app puede llamarse varias veces (tests)."""
    global _registrado
    if _registrado:
        return
    _registrado = True
    event_bus.subscribe("reports.reporte_emitido", on_reporte_emitido)
