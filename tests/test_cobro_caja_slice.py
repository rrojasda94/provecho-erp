"""Slice Cobro y Comprobante (PROC-COM-002) + ciclo de caja
(PROC-CTB-001/002): pago dividido, comprobante único por empresa+serie,
y la cadena apertura → custodia → cierre.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    CierreCaja,
    CustodiaEfectivo,
)
from src.modules.sales.infrastructure.models import MedioPago, Pago, Venta
from src.shared.models import Comprobante
from tests.test_venta_slice import _crear_cadena_base, _crear_trabajador


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_pago_dividido_suma_igual_a_total(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000006")

    efectivo = MedioPago(
        empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo"
    )
    tarjeta = MedioPago(
        empresa_id=empresa.id,
        nombre="Visa/Mastercard",
        direccion="cobro",
        tipo="tarjeta_debito",
    )
    session.add_all([efectivo, tarjeta])
    session.flush()

    venta = Venta(
        sucursal_id=sucursal.id,
        fecha_orden=date(2026, 7, 20),
        numero_orden=1,
        punto_venta_id=punto_venta.id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=usuario.id,
        total=Decimal("100.00"),
        idempotency_key=str(uuid.uuid4()),
    )
    session.add(venta)
    session.flush()

    session.add_all(
        [
            Pago(
                venta_id=venta.id,
                medio_pago_id=efectivo.id,
                monto=Decimal("40.00"),
                idempotency_key=str(uuid.uuid4()),
                estado="confirmado",
            ),
            Pago(
                venta_id=venta.id,
                medio_pago_id=tarjeta.id,
                monto=Decimal("60.00"),
                idempotency_key=str(uuid.uuid4()),
                estado="confirmado",
            ),
        ]
    )
    session.commit()

    pagos = session.query(Pago).filter_by(venta_id=venta.id).all()
    assert sum(p.monto for p in pagos) == venta.total


def test_comprobante_correlativo_unico_por_empresa_y_serie(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000007")

    venta = Venta(
        sucursal_id=sucursal.id,
        fecha_orden=date(2026, 7, 20),
        numero_orden=1,
        punto_venta_id=punto_venta.id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=usuario.id,
        total=Decimal("50.00"),
        idempotency_key=str(uuid.uuid4()),
    )
    session.add(venta)
    session.flush()

    session.add(
        Comprobante(
            empresa_id=empresa.id,
            venta_id=venta.id,
            punto_venta_id=punto_venta.id,
            direccion="emitido",
            tipo="boleta",
            serie=punto_venta.serie_boleta,
            correlativo=1,
            sustento="efectivo",
            idempotency_key=str(uuid.uuid4()),
        )
    )
    session.commit()

    session.add(
        Comprobante(
            empresa_id=empresa.id,
            venta_id=venta.id,
            punto_venta_id=punto_venta.id,
            direccion="emitido",
            tipo="boleta",
            serie=punto_venta.serie_boleta,
            correlativo=1,  # mismo correlativo, misma empresa+serie
            sustento="efectivo",
            idempotency_key=str(uuid.uuid4()),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_ciclo_apertura_custodia_cierre_caja(session):
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    cajero, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000008")
    supervisor, _ = _crear_trabajador(session, empresa, "Luis", "Super", "10000009")

    apertura = AperturaCaja(
        punto_venta_id=punto_venta.id,
        cajero_id=cajero.id,
        relevo_encargado_id=supervisor.id,
        monto_apertura=Decimal("200.00"),
    )
    session.add(apertura)
    session.flush()

    custodia = CustodiaEfectivo(
        apertura_caja_id=apertura.id,
        monto=Decimal("200.00"),
        responsable_actual_id=cajero.id,
        estado="en_caja",
    )
    session.add(custodia)
    session.flush()

    # Cierre: cadena de custodia avanza cajero -> supervisor.
    custodia.estado = "en_supervisor"
    custodia.responsable_actual_id = supervisor.id

    cierre = CierreCaja(
        apertura_caja_id=apertura.id,
        cajero_id=cajero.id,
        descuadre_monto=Decimal("0.00"),
        custodia="local_caja_fuerte",
        estado="conforme",
    )
    session.add(cierre)
    session.commit()

    assert cierre.apertura_caja_id == apertura.id
    assert custodia.estado == "en_supervisor"

    # 1:1 — un segundo cierre para la misma apertura viola la unicidad.
    session.add(
        CierreCaja(
            apertura_caja_id=apertura.id,
            cajero_id=cajero.id,
            custodia="traslado_contabilidad",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
