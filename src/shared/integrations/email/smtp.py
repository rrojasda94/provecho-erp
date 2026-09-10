"""Envío de correo por SMTP — el canal `email` de `reports` (ADR-033).

Solo `smtplib`/`email` de la librería estándar: es el primer canal más allá
de la bandeja y no hay todavía una segunda necesidad (SES, plantillas HTML
con tracking) que justifique cargar un cliente de terceros. Si aparece,
esto se reemplaza sin que `reports` ni `users` se enteren — ya hablan con
`enviar()`, no con `smtplib`.
"""

import logging
import smtplib
from email.message import EmailMessage

from src.config.settings import settings

log = logging.getLogger("provecho.app")


class EmailNoConfigurado(Exception):
    """Sin `SMTP_HOST` — no hay a dónde conectarse."""


def configurado() -> bool:
    return bool(settings.smtp_host)


def enviar(*, destinatario: str, asunto: str, cuerpo: str) -> None:
    """Manda un correo de texto plano. No reintenta: quien la llama decide
    qué hacer con el fallo (`reports`/`users` lo loguean y siguen — un
    correo caído no puede tumbar el resto de la distribución)."""
    if not configurado():
        raise EmailNoConfigurado("SMTP no está configurado (falta SMTP_HOST)")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = settings.smtp_from
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_segundos
    ) as cliente:
        if settings.smtp_use_tls:
            cliente.starttls()
        if settings.smtp_user:
            cliente.login(settings.smtp_user, settings.smtp_password)
        cliente.send_message(mensaje)
