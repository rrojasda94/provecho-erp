"""Adaptador de la WhatsApp Cloud API (Meta) — mensajería saliente y
entrante. Hoy lo usa la encuesta de satisfacción de `marketing`."""

from src.shared.integrations.whatsapp.client import (
    MAX_BOTONES,
    MAX_ITEMS_LISTA,
    MensajeEntrante,
    WhatsAppClient,
    WhatsAppError,
    WhatsAppRechazo,
    habilitado,
    interpretar_webhook,
    normalizar_telefono,
    verificar_firma,
)

__all__ = [
    "MAX_BOTONES",
    "MAX_ITEMS_LISTA",
    "MensajeEntrante",
    "WhatsAppClient",
    "WhatsAppError",
    "WhatsAppRechazo",
    "habilitado",
    "interpretar_webhook",
    "normalizar_telefono",
    "verificar_firma",
]
