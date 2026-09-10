"""Reglas de negocio de `assets`. Puras, sin infraestructura.

Cubre lo que RN-VEH-001..004, RN-MNT-001..004 y RN-EQP-001..004
(`docs/domain/business-rules.md`) especificaban sin código, más lo nuevo que
este módulo agrega: odómetro monótono, anomalía de consumo y vencimiento de
documentos.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

TIPOS_ACTIVO = ("equipamiento", "vehiculo")
ESTADOS_ACTIVO = ("operativo", "en_mantenimiento", "de_baja")
TIPOS_VEHICULO = ("moto", "auto", "camioneta", "camion", "otro")
TENENCIAS_VEHICULO = ("propio", "alquilado")
ORIGENES_LECTURA = ("manual", "carga_combustible", "mantenimiento")
TIPOS_ORDEN_MANTENIMIENTO = ("programado", "adelantado")
MOTIVOS_ADELANTO = ("desperfecto", "baja_productividad")
ESTADOS_ORDEN_MANTENIMIENTO = ("programada", "en_curso", "realizada", "cancelada")

# RN-MNT-001: cada activo tiene su frecuencia recomendada. El estado del plan
# es siempre uno de estos tres — nunca se persiste, se deriva.
ESTADOS_PLAN = ("al_dia", "proximo", "vencido")

# Catálogo cerrado de documentos de vigencia (equivalente al criterio de
# `reports.domain.catalogo`: una lista abierta por API dejaría registrar
# cualquier texto como "tipo de documento" y el filtro por tipo se rompería
# con el primer typo).
TIPOS_DOCUMENTO = (
    "soat",
    "revision_tecnica",
    "tarjeta_propiedad",
    "poliza_seguro",
    "garantia",
    "licencia_funcionamiento",
    "certificado_defensa_civil",
    "fumigacion",
    "registro_sanitario",
    "carne_sanidad",
    "licencia_conducir",
    "otro",
)
SUJETOS_DOCUMENTO = ("activo", "sucursal", "empresa", "trabajador")

DIAS_AVISO_MANTENIMIENTO_DEFECTO = 15
KM_AVISO_MANTENIMIENTO_DEFECTO = 500
DIAS_AVISO_DOCUMENTO_DEFECTO = 30

# Parámetro operativo (ADR-014): cuánto puede caer el rendimiento de una
# carga respecto al promedio de las anteriores antes de marcarla anómala.
TOLERANCIA_CONSUMO_PCT_DEFECTO = 25
# Con menos cargas previas que esto, el promedio es ruido: una sola carga
# mala no tiene con qué compararse todavía.
MINIMO_CARGAS_PARA_ANOMALIA = 3
VENTANA_PROMEDIO_CARGAS = 5


def odometro_valido(km_nuevo: int, km_actual: int | None) -> bool:
    """RN-VEH-005: el odómetro nunca retrocede. `km_actual` nulo = primera
    lectura del vehículo, siempre válida."""
    return km_actual is None or km_nuevo >= km_actual


def rendimiento_km_gal(km_recorridos: int, galones: Decimal) -> Decimal | None:
    """`None` cuando no hay distancia previa que comparar (primera carga del
    vehículo, o dos cargas el mismo día sin recorrido)."""
    if km_recorridos <= 0 or galones <= 0:
        return None
    return Decimal(km_recorridos) / galones


def es_consumo_anomalo(
    rendimiento: Decimal | None,
    rendimientos_previos: list[Decimal],
    *,
    tolerancia_pct: int = TOLERANCIA_CONSUMO_PCT_DEFECTO,
) -> bool:
    """RN-VEH-007: la carga rinde bien por debajo de su propio historial.

    Compara contra el promedio de hasta las últimas `VENTANA_PROMEDIO_CARGAS`
    cargas **anteriores** (nunca contra sí misma) y exige un mínimo de
    cargas previas: con una o dos, cualquier variación normal del tráfico
    parecería una anomalía.
    """
    if rendimiento is None:
        return False
    previos = [r for r in rendimientos_previos if r is not None]
    if len(previos) < MINIMO_CARGAS_PARA_ANOMALIA:
        return False
    muestra = previos[-VENTANA_PROMEDIO_CARGAS:]
    promedio = sum(muestra) / Decimal(len(muestra))
    if promedio <= 0:
        return False
    umbral = promedio * (Decimal(100 - tolerancia_pct) / Decimal(100))
    return rendimiento < umbral


@dataclass(frozen=True)
class EstadoPlan:
    estado: str
    proxima_fecha: date | None
    proximo_km: int | None


def estado_plan(
    *,
    hoy: date,
    cada_dias: int | None,
    cada_km: int | None,
    dias_aviso: int,
    km_aviso: int,
    ultima_fecha: date | None,
    fecha_base: date,
    ultimo_km: int | None,
    km_base: int | None,
    km_actual: int | None,
) -> EstadoPlan:
    """RN-MNT-005: el plan avisa con anticipación configurable, por fecha y/o
    por kilometraje — lo que se cumpla primero.

    `fecha_base`/`km_base` son el punto de partida cuando el plan nunca se
    ejecutó (alta del plan o del activo); `ultima_fecha`/`ultimo_km` ganan en
    cuanto existen.
    """
    proxima_fecha = None
    if cada_dias is not None:
        base = ultima_fecha or fecha_base
        proxima_fecha = base + timedelta(days=cada_dias)

    proximo_km = None
    if cada_km is not None and km_actual is not None:
        base_km = ultimo_km if ultimo_km is not None else (km_base or 0)
        proximo_km = base_km + cada_km

    vencido_por_fecha = proxima_fecha is not None and hoy >= proxima_fecha
    vencido_por_km = proximo_km is not None and km_actual is not None and km_actual >= proximo_km
    proximo_por_fecha = proxima_fecha is not None and hoy >= proxima_fecha - timedelta(
        days=dias_aviso
    )
    proximo_por_km = (
        proximo_km is not None and km_actual is not None and km_actual >= proximo_km - km_aviso
    )

    if vencido_por_fecha or vencido_por_km:
        estado = "vencido"
    elif proximo_por_fecha or proximo_por_km:
        estado = "proximo"
    else:
        estado = "al_dia"
    return EstadoPlan(estado=estado, proxima_fecha=proxima_fecha, proximo_km=proximo_km)


@dataclass(frozen=True)
class EstadoDocumento:
    estado: str  # vigente | proximo | vencido | renovado


def estado_documento(
    *, hoy: date, fecha_vencimiento: date, dias_aviso: int, renovado: bool
) -> EstadoDocumento:
    if renovado:
        return EstadoDocumento(estado="renovado")
    if hoy >= fecha_vencimiento:
        return EstadoDocumento(estado="vencido")
    if hoy >= fecha_vencimiento - timedelta(days=dias_aviso):
        return EstadoDocumento(estado="proximo")
    return EstadoDocumento(estado="vigente")


def puede_iniciar_orden(estado: str) -> bool:
    return estado == "programada"


def puede_realizar_orden(estado: str) -> bool:
    return estado in ("programada", "en_curso")


def puede_cancelar_orden(estado: str) -> bool:
    return estado in ("programada", "en_curso")
