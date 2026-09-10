"""Enlace público de seguimiento del cliente (RN-DLV-008, ADR-098).

El token es una credencial anónima: quien lo tenga ve el estado de esa
entrega y nada más. La respuesta es deliberadamente mínima — nunca monto,
teléfono, dirección en texto ni las demás paradas de la ruta (viven en la
misma `ruta_reparto`, y filtrarlas sería regalarle a cualquiera que
reenvíe el link por dónde anda el pedido de otro cliente). Mismo criterio
que `marketing.application.encuestas`, que ya resuelve este mismo
problema para la encuesta de satisfacción.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.delivery.domain import rules
from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo
from src.modules.rrhh.application.queries_publicas import cuenta_de_trabajador
from src.modules.sales.application.queries_publicas import venta_para_reparto
from src.modules.users.infrastructure.models import Sucursal

_ESTADO_PUBLICO = {
    "pendiente": "preparando",
    "asignada": "preparando",
    "en_ruta": "en_camino",
    "entregada": "entregado",
    "fallida": "no_entregado",
    "cancelada": "no_entregado",
}


def nuevo_token() -> str:
    """Credencial anónima del enlace. Se llama una vez por cada asignación
    a ruta (`application/rutas.py`) — reasignar una entrega a una salida
    nueva invalida cualquier link que ya se haya mandado de un intento
    anterior, en vez de dejarlo vivo apuntando a un estado viejo."""
    return secrets.token_urlsafe(32)


def token_expira_en(ahora: datetime | None = None) -> datetime:
    ahora = ahora or datetime.now(UTC)
    return ahora + timedelta(hours=settings.delivery_seguimiento_vigencia_horas)


def url_publica(token: str) -> str:
    """Vacío si `DELIVERY_URL_PUBLICA` no está configurada — mismo criterio
    que `marketing.application.encuestas.url_publica`: sin base, no hay
    enlace que mandar, y el llamador decide qué hacer con eso."""
    base = settings.delivery_url_publica.rstrip("/")
    return f"{base}/seguimiento/{token}" if base else ""


def _sin_zona(valor: datetime) -> datetime:
    """Compara en naive UTC: las columnas `DateTime(timezone=True)` de
    SQLite vuelven sin tzinfo tras un `commit`/recarga, y restarle un
    `datetime` con zona revienta (`sales.domain.rules._sin_zona` resuelve
    el mismo problema para `dentro_de_ventana`). Postgres sí conserva la
    zona, así que esto es un no-op ahí."""
    return valor.replace(tzinfo=None) if valor.tzinfo else valor


def por_token(session: Session, token: str, *, ahora: datetime | None = None) -> dict | None:
    """El mínimo que ve el cliente. `None` = token inexistente, vencido, o
    de una entrega ya cerrada sin vigencia — los tres casos responden
    igual (404 desde el router) para no confirmarle a quien reenvía el
    link que ese token existió alguna vez.
    """
    entrega = EntregaRepo(session).get_por_token(token)
    if entrega is None:
        return None
    ahora = ahora or datetime.now(UTC)
    if entrega.token_expira_at is not None and _sin_zona(entrega.token_expira_at) < _sin_zona(
        ahora
    ):
        return None
    return _dto(session, entrega)


def _dto(session: Session, entrega: Entrega) -> dict:
    venta = venta_para_reparto(session, entrega.venta_id)
    sucursal_nombre = session.scalar(
        select(Sucursal.nombre).where(Sucursal.id == entrega.sucursal_id)
    )
    ruta = session.get(RutaReparto, entrega.ruta_id) if entrega.ruta_id else None
    return {
        "estado_publico": _ESTADO_PUBLICO.get(entrega.estado, "preparando"),
        "numero_orden": venta["numero_orden"] if venta else None,
        "sucursal": {"nombre": sucursal_nombre or ""},
        "repartidor": _repartidor_de(session, entrega.repartidor_id),
        "eta_at": entrega.eta_at,
        "posicion": _posicion_de(entrega, ruta),
        "destino": {"lat": entrega.destino_lat, "lng": entrega.destino_lng},
        "linea_tiempo": _linea_tiempo(entrega, ruta),
    }


def _repartidor_de(session: Session, repartidor_id: uuid.UUID | None) -> dict | None:
    """Solo el primer nombre (RN-DLV-008): lo suficiente para que el
    cliente reconozca a quién le abre la puerta, no un dato completo de
    quién lo entrega."""
    if repartidor_id is None:
        return None
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None:
        return None
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    if cuenta is None:
        return None
    partes = (cuenta.get("nombre") or "").split()
    return {"nombre": partes[0]} if partes else None


def _posicion_de(entrega: Entrega, ruta: RutaReparto | None) -> dict | None:
    if not rules.expone_posicion(entrega.estado):
        return None
    if ruta is None or ruta.ultima_lat is None or ruta.ultima_lng is None:
        return None
    return {
        "lat": ruta.ultima_lat,
        "lng": ruta.ultima_lng,
        "registrado_at": ruta.ultima_posicion_at,
    }


def _linea_tiempo(entrega: Entrega, ruta: RutaReparto | None) -> list[dict]:
    hitos = []
    if ruta is not None and ruta.hora_salida is not None:
        hitos.append({"hito": "en_camino", "at": ruta.hora_salida})
    if entrega.estado == "entregada":
        hitos.append({"hito": "entregado", "at": entrega.fecha_entrega})
    elif entrega.estado in ("fallida", "cancelada"):
        # Sin columna propia para "cuándo pasó a fallida": `updated_at` es
        # la mejor aproximación sin agregar una columna solo para esto
        # (deuda menor, no declarada porque el costo de arreglarla es una
        # migración de una columna si algún día hace falta más precisión).
        hitos.append({"hito": "no_entregado", "at": entrega.updated_at})
    return hitos
