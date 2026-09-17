"""Vista compuesta del tablero de despacho (ADR-098): qué pedido delivery
está listo y todavía sin asignar, y qué rutas siguen vivas. No es un caso
de uso con efectos — solo arma lo que la pantalla necesita en una sola
consulta.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session

from src.modules.delivery.application.mi_reparto import ruta_con_paradas
from src.modules.delivery.infrastructure.repositories import EntregaRepo, RutaRepo
from src.modules.sales.application.queries_publicas import ventas_para_reparto


def sin_asignar(
    session: Session, sucursal_ids: Sequence[uuid.UUID], *, fecha: date | None = None
) -> list[dict]:
    """Ventas delivery ruteables que todavía no tienen una entrega abierta
    — listas o no (RN-DLV-001): el despacho arma la ruta desde que se toma
    el pedido, no cuando llega a cocina."""
    candidatas = ventas_para_reparto(session, sucursal_ids, fecha=fecha)
    if not candidatas:
        return []
    ruteadas = EntregaRepo(session).venta_ids_ya_ruteadas([v["id"] for v in candidatas])
    return [v for v in candidatas if v["id"] not in ruteadas]


def rutas_vivas(session: Session, sucursal_ids: Sequence[uuid.UUID]) -> list[dict]:
    return [
        ruta_con_paradas(session, ruta)
        for ruta in RutaRepo(session).vivas_de_sucursales(sucursal_ids)
    ]
