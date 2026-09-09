"""Vista compuesta de una ruta con sus paradas ya resueltas (ADR-098): ni
la PWA del repartidor (`GET /delivery/mi/rutas`) ni el tablero de despacho
(`GET /delivery/tablero`, ver `tablero.py`) llaman a `sales` ni a `rrhh`
por su cuenta — las dos comparten `ruta_con_paradas`. No es un caso de uso
con efectos, solo arma lo que cada pantalla necesita en una sola consulta.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.delivery.application.seguimiento import url_publica
from src.modules.delivery.infrastructure.models import Entrega, Repartidor, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RutaRepo
from src.modules.rrhh.application.queries_publicas import cuenta_de_trabajador
from src.modules.sales.application.queries_publicas import (
    contacto_de_cliente,
    venta_para_reparto,
)


def rutas_vivas(session: Session, repartidor_id: uuid.UUID) -> list[dict]:
    """Las rutas vivas de UN repartidor — `GET /delivery/mi/rutas`."""
    return [
        ruta_con_paradas(session, ruta)
        for ruta in RutaRepo(session).vivas_de_repartidor(repartidor_id)
    ]


def ruta_con_paradas(session: Session, ruta: RutaReparto) -> dict:
    return {
        "id": ruta.id,
        "sucursal_id": ruta.sucursal_id,
        "repartidor_id": ruta.repartidor_id,
        "repartidor_nombre": _nombre_repartidor(session, ruta.repartidor_id),
        "estado": ruta.estado,
        "hora_salida": ruta.hora_salida,
        "origen_lat": ruta.origen_lat,
        "origen_lng": ruta.origen_lng,
        "distancia_m": ruta.distancia_m,
        "duracion_seg": ruta.duracion_seg,
        "polyline": ruta.polyline,
        "ultima_lat": ruta.ultima_lat,
        "ultima_lng": ruta.ultima_lng,
        "ultima_posicion_at": ruta.ultima_posicion_at,
        "paradas": [_parada_de(session, e) for e in EntregaRepo(session).de_ruta(ruta.id)],
    }


def _nombre_repartidor(session: Session, repartidor_id: uuid.UUID) -> str | None:
    repartidor = session.get(Repartidor, repartidor_id)
    if repartidor is None:
        return None
    cuenta = cuenta_de_trabajador(session, repartidor.trabajador_id)
    return cuenta["nombre"] if cuenta else None


def _parada_de(session: Session, entrega: Entrega) -> dict:
    venta = venta_para_reparto(session, entrega.venta_id)
    contacto = (
        contacto_de_cliente(session, venta["cliente_id"])
        if venta and venta["cliente_id"]
        else None
    )
    return {
        "entrega_id": entrega.id,
        "venta_id": entrega.venta_id,
        "orden_parada": entrega.orden_parada,
        "estado": entrega.estado,
        "numero_orden": venta["numero_orden"] if venta else None,
        "direccion_entrega": venta["direccion_entrega"] if venta else None,
        "destino_lat": entrega.destino_lat,
        "destino_lng": entrega.destino_lng,
        "cliente_nombre": contacto["nombre"] if contacto else None,
        "cliente_telefono": contacto["telefono"] if contacto else None,
        "monto_a_cobrar": venta["total"] if venta and venta["estado"] == "orden" else None,
        "eta_at": entrega.eta_at,
        "motivo_fallo": entrega.motivo_fallo,
        # Mismo enlace que recibe el cliente por WhatsApp — el tablero lo
        # ofrece para copiar o mandar por `wa.me` cuando el aviso
        # automático no está configurado (o como refuerzo si sí lo está).
        "enlace_seguimiento": (
            url_publica(entrega.token_publico) if entrega.token_publico else None
        )
        or None,
    }
