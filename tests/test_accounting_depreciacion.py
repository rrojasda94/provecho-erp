"""Depreciación lineal mensual de los activos de `assets` (PROC-CTB-007/010).

Prueba el caso de uso directamente (sin API ni Celery): un activo, un mes,
un asiento. `assets.activos_depreciables` y `accounting.crear_asiento_
automatico` ya se prueban por su cuenta en sus propios módulos.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.accounting.application import depreciacion
from src.modules.accounting.application import pcge as pcge_uc
from src.modules.accounting.infrastructure.models import (
    ActivoDepreciacion,
    Asiento,
    AsientoLinea,
    AsientoOmitido,
)
from src.modules.assets.infrastructure.models import Activo
from src.modules.users.infrastructure.models import Empresa, Grupo


@pytest.fixture()
def env(_engine_de_prueba):
    engine = _engine_de_prueba
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        grupo = Grupo(nombre="Grupo Majambo")
        s.add(grupo)
        s.flush()
        empresa = Empresa(
            grupo_id=grupo.id,
            razon_social="Majambo EIRL",
            ruc="20100000001",
            domicilio_fiscal="Jr. X 1",
            tipo="operativa",
        )
        s.add(empresa)
        s.flush()
        pcge_uc.importar_pcge(s, empresa_id=empresa.id)
        s.commit()
        yield s, empresa


def _crear_activo(
    s,
    empresa,
    *,
    id_interno="EQ001",
    valor_compra="1200.00",
    vida_util_meses=12,
    fecha_compra=None,
    estado="operativo",
) -> Activo:
    activo = Activo(
        empresa_id=empresa.id,
        tipo="equipamiento",
        id_interno=id_interno,
        nombre="Horno pizzero",
        valor_compra=Decimal(valor_compra),
        vida_util_meses=vida_util_meses,
        fecha_compra=fecha_compra or date(2026, 1, 1),
        estado=estado,
    )
    s.add(activo)
    s.flush()
    return activo


def test_genera_un_asiento_por_activo_y_acumula(env):
    s, empresa = env
    activo = _crear_activo(s, empresa)

    resultado = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 15))
    s.commit()
    assert resultado == {"generados": 1, "omitidos": 0}

    asiento = s.scalar(select(Asiento).where(Asiento.evento_origen == depreciacion.EVENTO))
    assert asiento is not None
    assert asiento.referencia_origen == f"{activo.id}:2026-06"

    lineas = list(s.scalars(select(AsientoLinea).where(AsientoLinea.asiento_id == asiento.id)))
    assert len(lineas) == 2
    cuota_esperada = (Decimal("1200.00") / 12).quantize(Decimal("0.01"))
    assert all(li.monto == cuota_esperada for li in lineas)
    assert {li.tipo for li in lineas} == {"debe", "haber"}

    tracking = s.scalar(select(ActivoDepreciacion).where(ActivoDepreciacion.activo_id == activo.id))
    assert tracking.depreciado_acumulado == cuota_esperada


def test_reintentar_el_mismo_mes_no_duplica(env):
    s, empresa = env
    _crear_activo(s, empresa)

    depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 5))
    s.commit()
    otra_vez = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 20))
    s.commit()

    assert otra_vez == {"generados": 0, "omitidos": 1}
    asientos = list(s.scalars(select(Asiento).where(Asiento.evento_origen == depreciacion.EVENTO)))
    assert len(asientos) == 1


def test_activo_de_baja_no_acumula_mas(env):
    s, empresa = env
    _crear_activo(s, empresa, estado="de_baja")

    resultado = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 15))
    s.commit()
    assert resultado == {"generados": 0, "omitidos": 0}


def test_se_detiene_al_depreciar_el_valor_completo(env):
    s, empresa = env
    activo = _crear_activo(
        s, empresa, valor_compra="100.00", vida_util_meses=2, fecha_compra=date(2026, 1, 1)
    )

    depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 1, 15))
    s.commit()
    depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 2, 15))
    s.commit()
    tercero = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 3, 15))
    s.commit()

    assert tercero == {"generados": 0, "omitidos": 0}
    tracking = s.scalar(select(ActivoDepreciacion).where(ActivoDepreciacion.activo_id == activo.id))
    assert tracking.depreciado_acumulado == Decimal("100.00")


def test_sin_cuentas_deja_asiento_omitido(env):
    s, empresa = env
    # Empresa sin PCGE importado: le faltan 6813/3913.
    grupo2 = Grupo(nombre="Otro grupo")
    s.add(grupo2)
    s.flush()
    otra_empresa = Empresa(
        grupo_id=grupo2.id,
        razon_social="Sin Cuentas SAC",
        ruc="20999999998",
        domicilio_fiscal="Jr. Z 1",
        tipo="operativa",
    )
    s.add(otra_empresa)
    s.flush()
    _crear_activo(s, otra_empresa, id_interno="EQ002")

    resultado = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 15))
    s.commit()
    assert resultado == {"generados": 0, "omitidos": 1}

    omitido = s.scalar(select(AsientoOmitido).where(AsientoOmitido.empresa_id == otra_empresa.id))
    assert omitido is not None
    assert omitido.motivo == "sin_cuentas"


def test_activo_sin_valor_de_compra_no_entra_al_barrido(env):
    s, empresa = env
    activo = Activo(
        empresa_id=empresa.id,
        tipo="equipamiento",
        id_interno="EQ003",
        nombre="Extintor",
    )
    s.add(activo)
    s.flush()

    resultado = depreciacion.correr_depreciacion_mensual(s, hoy=date(2026, 6, 15))
    s.commit()
    assert resultado == {"generados": 0, "omitidos": 0}
