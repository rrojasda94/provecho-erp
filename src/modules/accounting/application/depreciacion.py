"""Depreciación lineal mensual de los activos de `assets` (PROC-CTB-010).

Un asiento por activo por mes: debe `6813` (Depreciación de propiedad,
planta y equipo — Costo), haber `3913` (Depreciación acumulada — Propiedad,
planta y equipo). La cuota es lineal: `valor_compra / vida_util_meses`,
capada a lo que falte por depreciar en el último mes. `activo_depreciacion`
lleva la cuenta de lo ya depreciado; `asiento.referencia_origen`
(`<activo_id>:<AAAA-MM>`) es lo que hace idempotente volver a correr el
barrido el mismo mes — lo resuelve `crear_asiento_automatico`, que ya lo
hace para todo asiento automático del ERP.
"""

import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src.modules.accounting.application import asientos as asientos_uc
from src.modules.accounting.infrastructure.models import ActivoDepreciacion, AsientoOmitido
from src.modules.accounting.infrastructure.repositories import (
    ActivoDepreciacionRepo,
    AsientoOmitidoRepo,
    CuentaContableRepo,
)
from src.modules.assets.application.queries_publicas import activos_depreciables
from src.shared import fechas

log = logging.getLogger(__name__)

EVENTO = "accounting.depreciacion_mensual"
CODIGO_CUENTA_GASTO = "6813"
CODIGO_CUENTA_ACUMULADA = "3913"


def _tracking_de(session: Session, activo: dict) -> ActivoDepreciacion:
    repo = ActivoDepreciacionRepo(session)
    fila = repo.get_por_activo(activo["id"])
    if fila is not None:
        return fila
    return repo.add(
        ActivoDepreciacion(
            empresa_id=activo["empresa_id"],
            activo_id=activo["id"],
            valor_compra=activo["valor_compra"],
            vida_util_meses=activo["vida_util_meses"],
            fecha_inicio=activo["fecha_compra"],
            depreciado_acumulado=Decimal(0),
        )
    )


def _cuota_del_mes(tracking: ActivoDepreciacion) -> Decimal:
    pendiente = tracking.valor_compra - tracking.depreciado_acumulado
    if pendiente <= 0:
        return Decimal(0)
    lineal = tracking.valor_compra / tracking.vida_util_meses
    cuota = min(lineal, pendiente)
    return cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def correr_depreciacion_mensual(session: Session, *, hoy: date | None = None) -> dict:
    """Un barrido, todas las empresas — mismo criterio que
    `assets.avisos.barrer`: se corre una vez (Celery beat, día 1) y es
    idempotente si se vuelve a correr el mismo mes."""
    hoy = hoy or fechas.hoy()
    fecha_asiento = hoy.replace(day=1)
    periodo_str = fecha_asiento.strftime("%Y-%m")

    generados = 0
    omitidos = 0
    cuentas_repo = CuentaContableRepo(session)
    cuentas_por_empresa: dict[uuid.UUID, dict[str, uuid.UUID]] = {}

    for activo in activos_depreciables(session):
        empresa_id = activo["empresa_id"]
        if empresa_id not in cuentas_por_empresa:
            cuentas = cuentas_repo.get_by_codigos(
                empresa_id, [CODIGO_CUENTA_GASTO, CODIGO_CUENTA_ACUMULADA]
            )
            cuentas_por_empresa[empresa_id] = {
                codigo: cuenta.id for codigo, cuenta in cuentas.items()
            }
        cuentas = cuentas_por_empresa[empresa_id]
        if CODIGO_CUENTA_GASTO not in cuentas or CODIGO_CUENTA_ACUMULADA not in cuentas:
            log.warning(
                "depreciación omitida (sin_cuentas) activo=%s empresa=%s",
                activo["id"],
                empresa_id,
            )
            AsientoOmitidoRepo(session).add(
                AsientoOmitido(
                    empresa_id=empresa_id,
                    evento=EVENTO,
                    referencia_origen=f"{activo['id']}:{periodo_str}",
                    motivo="sin_cuentas",
                    fecha=fecha_asiento,
                    detalle=f"faltan las cuentas {CODIGO_CUENTA_GASTO}/{CODIGO_CUENTA_ACUMULADA}",
                )
            )
            omitidos += 1
            continue

        tracking = _tracking_de(session, activo)
        cuota = _cuota_del_mes(tracking)
        if cuota <= 0:
            continue  # ya depreciado del todo — nada que asentar

        asiento = asientos_uc.crear_asiento_automatico(
            session,
            empresa_id=empresa_id,
            evento=EVENTO,
            fecha=fecha_asiento,
            glosa=f"Depreciación {periodo_str} — {activo['nombre']}",
            referencia_origen=f"{activo['id']}:{periodo_str}",
            monto=cuota,
            cuenta_debe_id=cuentas[CODIGO_CUENTA_GASTO],
            cuenta_haber_id=cuentas[CODIGO_CUENTA_ACUMULADA],
        )
        if asiento is not None:
            tracking.depreciado_acumulado += cuota
            generados += 1
        else:
            omitidos += 1

    return {"generados": generados, "omitidos": omitidos}
