"""Pasarela de pagos Izipay (ADR-003, adaptador único en `src/shared/
integrations/`; puerto de pagos agnóstico para el módulo `sales`).

Sin credenciales reales de comercio en este entorno, el checkout del sitio
de marca (ADR-105) necesita poder cobrar "de mentira" para que todo
el flujo — crear el pedido, cobrar, emitir comprobante — se pueda probar de
punta a punta. `pasarela_activa()` decide entre `IzipayFake` (por defecto,
deja el pago pendiente) e `IzipayReal` (cuando alguien carga
`IZIPAY_API_KEY`), mismo criterio que `comprobantes.emision_habilitada()`
usa para Factiliza: "sin credencial configurada" es el estado normal antes
de ir a producción, no un error.

`IzipayFake` deja el intento **pendiente** y espera un webhook, igual que la
pasarela real: así la pantalla de pago, el webhook idempotente y el paso
"pedido pendiente -> venta" se prueban de verdad. El webhook de mentira solo se
acepta fuera de producción: en producción sin credenciales no hay forma de
aprobar un pago (`izipay_disponible()` corta antes, en el checkout).

`IzipayReal` queda como esqueleto: sin una cuenta de comercio real contra
la cual probar el flujo de redirección/webhook, completarlo a ciegas sería
código sin forma de verificarse. Ver `docs/roadmap/deuda/modulo-storefront.md`.
"""

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.config.settings import settings


class IzipayError(RuntimeError):
    """Fallo de transporte o respuesta ilegible de la pasarela. Reintentable."""


@dataclass(frozen=True)
class IntentoPago:
    """Lo que la pasarela devuelve al iniciar un cobro."""

    id_externo: str
    # `aprobado` de inmediato (billetera/tarjeta ya autorizada en la propia
    # pasarela) o `pendiente` (falta que el cliente termine el pago en
    # `url_pago`, ej. una redirección 3DS). `IzipayFake` siempre aprueba.
    estado: str
    url_pago: str | None = None


@dataclass(frozen=True)
class ResultadoWebhook:
    id_externo: str
    aprobado: bool
    monto: Decimal | None = None


class Pasarela(Protocol):
    def crear_intento(
        self, *, monto: Decimal, moneda: str, referencia: str, medio: str
    ) -> IntentoPago: ...

    def verificar_webhook(self, payload: bytes, firma: str) -> ResultadoWebhook: ...


class IzipayFake:
    """Cobra "de mentira": el intento queda pendiente y el resultado llega por
    webhook (la pantalla de pago de prueba lo manda). Para desarrollo, tests y
    staging mientras Grupo Majambo no tenga una cuenta de comercio real."""

    def crear_intento(
        self, *, monto: Decimal, moneda: str, referencia: str, medio: str
    ) -> IntentoPago:
        return IntentoPago(id_externo=f"fake-{uuid.uuid4()}", estado="pendiente")

    def verificar_webhook(self, payload: bytes, firma: str) -> ResultadoWebhook:
        """La "firma" del webhook de mentira es el resultado que se quiere
        simular (`aprobado` | `rechazado`); el cuerpo trae `{"id_externo": ...}`.
        Nunca en producción: sería una puerta abierta para marcar pedidos como
        pagados sin pagar."""
        if settings.es_produccion:
            raise IzipayError("el webhook de prueba no existe en producción")
        if firma not in ("aprobado", "rechazado"):
            raise IzipayError("resultado de prueba inválido (aprobado | rechazado)")
        try:
            id_externo = json.loads(payload)["id_externo"]
        except (ValueError, KeyError, TypeError) as e:
            raise IzipayError("cuerpo del webhook de prueba ilegible") from e
        return ResultadoWebhook(id_externo=str(id_externo), aprobado=firma == "aprobado")


class IzipayReal:
    """Esqueleto del adaptador real. Sin credenciales de comercio contra las
    que probar el intercambio real de la API de Izipay, completar
    `crear_intento`/`verificar_webhook` sin poder verificarlos sería peor
    que dejarlos explícitamente sin implementar."""

    def __init__(self, api_key: str, webhook_secret: str) -> None:
        self.api_key = api_key
        self.webhook_secret = webhook_secret

    def crear_intento(
        self, *, monto: Decimal, moneda: str, referencia: str, medio: str
    ) -> IntentoPago:
        raise NotImplementedError(
            "IzipayReal.crear_intento: pendiente de credenciales de comercio "
            "reales para implementar y probar contra la API de Izipay"
        )

    def verificar_webhook(self, payload: bytes, firma: str) -> ResultadoWebhook:
        raise NotImplementedError(
            "IzipayReal.verificar_webhook: pendiente de credenciales reales"
        )


def izipay_habilitado() -> bool:
    """Sin `IZIPAY_API_KEY` configurada, el checkout usa la pasarela falsa:
    el sitio sigue operando (con efectivo, y con un Izipay que aprueba de
    inmediato) mientras no exista una cuenta de comercio real."""
    return bool(settings.izipay_api_key)


def izipay_disponible() -> bool:
    """¿Se puede cobrar con Izipay ahora? Con credenciales, sí. Sin ellas solo
    fuera de producción (pasarela de mentira): en producción, aceptar un pago
    que nadie cobra sería regalar comida."""
    return izipay_habilitado() or not settings.es_produccion


def pasarela_activa() -> Pasarela:
    if izipay_habilitado():
        return IzipayReal(settings.izipay_api_key, settings.izipay_webhook_secret)
    return IzipayFake()
