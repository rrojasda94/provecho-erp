"""Carga de combustible: liga un comprobante ya recibido en `purchases` al
vehículo, y calcula su rendimiento contra el historial (RN-VEH-006/007).

El comprobante nace en Compras (compra directa con un artículo `tipo=
"servicio"` — no hay flujo de gasto propio en `assets`, decisión con el
usuario 2026-09-09): acá solo se consume su id.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.assets.application import vehiculos as vehiculos_uc
from src.modules.assets.application.errors import Conflicto
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import CargaCombustible, Vehiculo
from src.modules.assets.infrastructure.repositories import (
    ActivoRepo,
    CargaCombustibleRepo,
)
from src.shared import parametros

CODIGO_TOLERANCIA = "tolerancia_consumo_pct"


def tolerancia_consumo(session: Session, empresa_id: uuid.UUID) -> int:
    valor = parametros.valor_vigente(session, empresa_id, "assets", CODIGO_TOLERANCIA, default=None)
    if isinstance(valor, dict) and "porcentaje" in valor:
        return int(valor["porcentaje"])
    return rules.TOLERANCIA_CONSUMO_PCT_DEFECTO


def registrar_carga(
    session: Session,
    vehiculo: Vehiculo,
    *,
    comprobante_id: uuid.UUID,
    fecha: date,
    galones: Decimal,
    monto: Decimal,
    km_odometro: int,
    registrado_por: uuid.UUID,
    tipo_combustible: str | None = None,
) -> CargaCombustible:
    repo = CargaCombustibleRepo(session)
    if repo.get_by_comprobante(comprobante_id) is not None:
        raise Conflicto("ese comprobante ya sustenta otra carga de combustible")

    empresa_id = ActivoRepo(session).get(vehiculo.activo_id).empresa_id
    anterior = repo.ultima_de_vehiculo(vehiculo.activo_id)
    km_recorridos = km_odometro - anterior.km_odometro if anterior is not None else None
    rendimiento = (
        rules.rendimiento_km_gal(km_recorridos, galones) if km_recorridos is not None else None
    )
    previos = repo.rendimientos_previos(vehiculo.activo_id, limite=rules.VENTANA_PROMEDIO_CARGAS)
    tolerancia = tolerancia_consumo(session, empresa_id)
    anomalo = rules.es_consumo_anomalo(rendimiento, previos, tolerancia_pct=tolerancia)

    # RN-VEH-005: valida y actualiza el odómetro antes de persistir la carga,
    # así una lectura inválida no deja una carga a medio guardar.
    vehiculos_uc.registrar_lectura(
        session,
        vehiculo,
        km=km_odometro,
        fecha=fecha,
        origen="carga_combustible",
        registrado_por=registrado_por,
    )

    carga = repo.add(
        CargaCombustible(
            vehiculo_id=vehiculo.activo_id,
            fecha=fecha,
            galones=galones,
            monto=monto,
            tipo_combustible=tipo_combustible,
            km_odometro=km_odometro,
            comprobante_id=comprobante_id,
            km_recorridos=km_recorridos,
            rendimiento_km_gal=rendimiento,
            anomalo=anomalo,
            registrado_por=registrado_por,
        )
    )

    if anomalo:
        event_bus.publish(
            "assets.consumo_anomalo",
            {
                "carga_id": str(carga.id),
                "activo_id": str(vehiculo.activo_id),
                "empresa_id": str(empresa_id),
                "rendimiento_km_gal": str(rendimiento),
                "galones": str(galones),
                "km_recorridos": km_recorridos,
                "registrado_por": str(registrado_por),
            },
            session=session,
        )
    return carga


def q_cargas(session: Session, vehiculo_id: uuid.UUID):
    return CargaCombustibleRepo(session).q_de_vehiculo(vehiculo_id)


def resumen_consumo(session: Session, vehiculo_id: uuid.UUID) -> dict:
    cargas = CargaCombustibleRepo(session).list_de_vehiculo(vehiculo_id)
    con_rendimiento = [c.rendimiento_km_gal for c in cargas if c.rendimiento_km_gal]
    promedio = sum(con_rendimiento) / Decimal(len(con_rendimiento)) if con_rendimiento else None
    return {
        "cargas": len(cargas),
        "promedio_km_gal": promedio,
        "anomalas": sum(1 for c in cargas if c.anomalo),
    }
