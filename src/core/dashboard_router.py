"""Dashboard gerencial: agregado de solo lectura de ventas, stock y caja.

Vive en `core` y no en un módulo de negocio porque compone contratos
públicos de *varios* módulos (`sales`, `inventory`, `accounting`) — igual
que `core/app.py` ya ensambla los routers de todos los módulos, este
router ensambla sus lecturas públicas. Nunca importa el dominio de ninguno
directo, solo sus funciones `application`/`queries_publicas` ya pensadas
para consumo externo.

`empresa_id` como query param, no derivado del JWT — mismo patrón (y misma
deuda declarada, ADR-004) que el resto de la API hoy.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.modules.accounting.application import caja
from src.modules.inventory.application.stock import contar_bajo_minimo
from src.modules.sales.application.queries_publicas import resumen_ventas_del_dia
from src.modules.users.api.deps import get_db, require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

LEER = "dashboard.leer"


# Schemas propios del agregador: no pertenecen a un solo módulo, así que no
# viven en el `api/schemas.py` de ninguno (mismo criterio que este router
# viviendo en `core`, no en un módulo de negocio).
class VentasHoyOut(BaseModel):
    fecha: date
    cantidad: int
    total: Decimal


class CajaAbiertaOut(BaseModel):
    apertura_caja_id: uuid.UUID
    punto_venta_id: uuid.UUID
    cajero_id: uuid.UUID
    monto_apertura: Decimal
    abierta_desde: datetime


class DashboardResumenOut(BaseModel):
    ventas_hoy: VentasHoyOut
    stock_bajo_minimo: int
    cajas_abiertas: list[CajaAbiertaOut]


@router.get("/resumen", response_model=DashboardResumenOut)
def resumen(
    empresa_id: uuid.UUID,
    _=Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return {
        "ventas_hoy": resumen_ventas_del_dia(session, empresa_id),
        "stock_bajo_minimo": contar_bajo_minimo(session, empresa_id),
        "cajas_abiertas": caja.cajas_abiertas(session, empresa_id),
    }
