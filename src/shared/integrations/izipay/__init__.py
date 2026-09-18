"""Pasarela de pagos Izipay (ADR-003, adaptador único en `src/shared/
integrations/`; puerto de pagos agnóstico para el módulo `sales`).

Sin credenciales reales de comercio en este entorno, el checkout del sitio
de marca (ADR-105) necesita poder cobrar "de mentira" para que todo
el flujo — crear el pedido, cobrar, emitir comprobante — se pueda probar de
punta a punta. `pasarela_activa()` decide entre `IzipayFake` (por defecto,
aprueba de inmediato) e `IzipayReal` (cuando alguien carga
`IZIPAY_API_KEY`), mismo criterio que `comprobantes.emision_habilitada()`
usa para Factiliza: "sin credencial configurada" es el estado normal antes
de ir a producción, no un error.

`IzipayReal` queda como esqueleto: sin una cuenta de comercio real contra
la cual probar el flujo de redirección/webhook, completarlo a ciegas sería
código sin forma de verificarse. Ver `docs/roadmap/deuda/modulo-storefront.md`.
"""

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
    """Aprueba cualquier cobro de inmediato — para desarrollo, tests y
    mientras Grupo Majambo no tenga una cuenta de comercio real."""

    def crear_intento(
        self, *, monto: Decimal, moneda: str, referencia: str, medio: str
    ) -> IntentoPago:
        return IntentoPago(id_externo=f"fake-{uuid.uuid4()}", estado="aprobado")

    def verificar_webhook(self, payload: bytes, firma: str) -> ResultadoWebhook:
        raise IzipayError("IzipayFake no recibe webhooks: aprueba en el propio checkout")


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


def pasarela_activa() -> Pasarela:
    if izipay_habilitado():
        return IzipayReal(settings.izipay_api_key, settings.izipay_webhook_secret)
    return IzipayFake()
