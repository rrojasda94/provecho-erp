"""Vista compuesta de la PWA del repartidor (ADR-098): sus rutas vivas con
cada parada ya resuelta contra la venta y el contacto del cliente. No es un
caso de uso con efectos — solo arma lo que `GET /delivery/mi/rutas`
necesita en una sola consulta, igual que `tablero.py` para el despacho.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.delivery.infrastructure.models import Entrega, RutaReparto
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RutaRepo
from src.modules.sales.application.queries_publicas import (
    contacto_de_cliente,
    venta_para_reparto,
)


def rutas_vivas(session: Session, repartidor_id: uuid.UUID) -> list[dict]:
    return [
        _con_paradas(session, ruta) for ruta in RutaRepo(session).vivas_de_repartidor(repartidor_id)
    ]


def _con_paradas(session: Session, ruta: RutaReparto) -> dict:
    return {
        "id": ruta.id,
        "sucursal_id": ruta.sucursal_id,
        "estado": ruta.estado,
        "hora_salida": ruta.hora_salida,
        "origen_lat": ruta.origen_lat,
        "origen_lng": ruta.origen_lng,
        "distancia_m": ruta.distancia_m,
        "duracion_seg": ruta.duracion_seg,
        "ultima_lat": ruta.ultima_lat,
        "ultima_lng": ruta.ultima_lng,
        "ultima_posicion_at": ruta.ultima_posicion_at,
        "paradas": [_parada_de(session, e) for e in EntregaRepo(session).de_ruta(ruta.id)],
    }


def _parada_de(session: Session, entrega: Entrega) -> dict:
    venta = venta_para_reparto(session, entrega.venta_id)
    contacto = (
        contacto_de_cliente(session, venta["cliente_id"]) if venta and venta["cliente_id"] else None
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
        # Solo se cobra en la puerta si la venta sigue `orden` (sin pagar
        # todavía) — pagada o facturada ya se cobró en caja.
        "monto_a_cobrar": venta["total"] if venta and venta["estado"] == "orden" else None,
        "eta_at": entrega.eta_at,
        "motivo_fallo": entrega.motivo_fallo,
    }
