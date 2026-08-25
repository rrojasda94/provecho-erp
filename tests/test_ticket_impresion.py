"""Representación impresa en ticketera de 80 mm (ADR-066).

Lo que se prueba acá es que el papel y el XML digan lo mismo: los totales
del ticket salen del mismo payload que se le manda a Factiliza, el QR
codifica esos mismos importes, y la fecha del documento es la del cobro y
no la del momento en que alguien lo imprime.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import comprobantes, impresion
from src.modules.sales.domain import qr_sunat
from src.modules.sales.infrastructure.repositories import ComprobanteRepo
from src.modules.users.infrastructure.models import Marca
from src.shared import impresion as papel
from src.shared.integrations import factiliza
from tests.test_facturacion_electronica import _venta_pagada


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# --- Ancho del papel ---------------------------------------------------------
def test_todo_lo_impreso_usa_el_mismo_ancho() -> None:
    """80 mm son 48 columnas y no hay una segunda medida: la comanda usaba
    32 (58 mm) y la precuenta 40, y el mismo rollo salía con tres márgenes."""
    from src.modules.sales.application import kds, precuenta

    assert papel.ANCHO == 48
    assert kds.ANCHO_COMANDA == papel.ANCHO
    assert precuenta.ANCHO == papel.ANCHO


def test_el_monto_queda_pegado_al_borde_derecho() -> None:
    linea = papel.monto("Subtotal", Decimal("35.5"))
    assert len(linea) == papel.ANCHO
    assert linea.endswith("S/ 35.50")


def test_una_etiqueta_larga_se_corta_antes_que_el_monto() -> None:
    """Un nombre truncado se entiende; un total truncado es un error."""
    linea = papel.monto("X" * 200, Decimal("9.90"))
    assert len(linea) == papel.ANCHO
    assert linea.endswith("S/ 9.90")


# --- Cadena del QR -----------------------------------------------------------
def test_el_qr_lleva_los_nueve_campos_del_anexo_de_sunat() -> None:
    cadena = qr_sunat.cadena(
        ruc_emisor="20450311520",
        tipo_doc=factiliza.TIPO_DOC_BOLETA,
        serie="B001",
        correlativo=7,
        igv=Decimal("18"),
        total=Decimal("118"),
        fecha_emision=datetime(2026, 8, 25).date(),
        tipo_doc_receptor="1",
        num_doc_receptor="12345678",
    )
    assert cadena == "20450311520|03|B001|7|18.00|118.00|2026-08-25|1|12345678|"
    # Nueve campos y el separador de cierre: el `split` da diez pedazos, el
    # último vacío. Es lo que valida el lector de SUNAT.
    assert len(cadena.split("|")) == 10
    assert cadena.split("|")[-1] == ""


# --- Ticket del comprobante --------------------------------------------------
def test_el_ticket_declara_los_mismos_totales_que_el_xml(session) -> None:
    """No recalcula: lee el payload que se le manda a Factiliza. Si el ticket
    sumara por su cuenta, el papel y SUNAT podrían discrepar en un céntimo."""
    _empresa, _venta, comprobante = _venta_pagada(session)
    payload = factiliza.construir_payload(
        comprobantes.documento_de(session, comprobante)
    )

    ticket = impresion.ticket_comprobante(session, comprobante.id)

    assert ticket["totales"]["total"] == Decimal(str(payload["monto_Imp_Venta"]))
    assert ticket["totales"]["igv"] == Decimal(str(payload["monto_Igv"]))
    assert ticket["totales"]["gravadas"] == Decimal(
        str(payload["monto_Oper_Gravadas"])
    )
    assert ticket["totales"]["exoneradas"] == Decimal(
        str(payload["monto_Oper_Exoneradas"])
    )
    assert len(ticket["items"]) == len(payload["detalle"])


def test_el_item_del_ticket_muestra_el_precio_con_igv(session) -> None:
    """Es lo que el cliente compara contra la carta. El desglose imponible
    vive en el bloque de totales, no en la línea."""
    _empresa, _venta, comprobante = _venta_pagada(session)
    ticket = impresion.ticket_comprobante(session, comprobante.id)
    linea = ticket["items"][0]
    assert linea["precio_unitario"] == Decimal("118.00")
    assert linea["importe"] == linea["cantidad"] * linea["precio_unitario"]
    assert ticket["totales"]["total"] == linea["importe"]


def test_el_qr_del_ticket_codifica_el_documento_emitido(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session)
    ticket = impresion.ticket_comprobante(session, comprobante.id)

    campos = ticket["pie"]["qr_texto"].split("|")
    assert campos[0] == "20450311520"
    assert campos[1] == factiliza.TIPO_DOC_BOLETA
    assert campos[2] == comprobante.serie
    assert campos[3] == str(comprobante.correlativo)
    assert Decimal(campos[5]) == ticket["totales"]["total"]
    assert ticket["pie"]["qr_imagen"].startswith("data:image/svg+xml")


def test_el_ticket_sale_aunque_sunat_no_haya_contestado(session) -> None:
    """La emisión es asíncrona a propósito (RN-COM-003): el cliente se lleva
    su papel en caja. Lo que cambia es la franja, no la existencia."""
    _empresa, _venta, comprobante = _venta_pagada(session)
    assert comprobante.estado_emision == "pendiente"

    ticket = impresion.ticket_comprobante(session, comprobante.id)
    assert ticket["documento"]["aviso"] == "PENDIENTE DE ENVÍO A SUNAT"

    comprobante.estado_emision = "aceptado"
    comprobante.hash_proveedor = "AeOqQVd8d5kfPS+CmeCMF+NNMpI="
    session.flush()
    aceptado = impresion.ticket_comprobante(session, comprobante.id)
    assert aceptado["documento"]["aviso"] is None
    assert aceptado["pie"]["hash"] == "AeOqQVd8d5kfPS+CmeCMF+NNMpI="


def test_el_encabezado_sale_del_padron_y_no_de_lo_que_teclee_el_local(
    session,
) -> None:
    _empresa, venta, comprobante = _venta_pagada(session)
    ticket = impresion.ticket_comprobante(session, comprobante.id)
    cabecera = ticket["encabezado"]
    assert cabecera["ruc"] == "20450311520"
    assert cabecera["razon_social"] == "Majambo EIRL"
    assert cabecera["marca"] == "Charlie's Pizzas"
    assert cabecera["sucursal"] == "Charlie's - Plaza"


def test_el_logo_y_el_pie_se_configuran_por_marca(session) -> None:
    """En `marca.skins`, la columna que ya existía para el branding del PDV:
    dos campos de texto no justifican una tabla ni una migración."""
    _empresa, venta, _comprobante = _venta_pagada(session)
    sucursal_id = venta.sucursal_id
    sucursal = ComprobanteRepo(session).sucursal(sucursal_id)
    marca = session.get(Marca, sucursal.marca_id)
    marca.skins = {"ticket": {"logo": "/marcas/charlies.svg", "pie": ["Gracias!"]}}
    session.flush()

    cabecera = impresion.encabezado(session, sucursal_id)
    assert cabecera["logo"] == "/marcas/charlies.svg"
    assert cabecera["pie"] == ["Gracias!"]


# --- Fecha del documento -----------------------------------------------------
def test_el_documento_declara_la_fecha_del_cobro_y_no_la_de_hoy(session) -> None:
    """Un comprobante que se quedó en la cola y sale al día siguiente sigue
    documentando la venta de ayer. Con `now()` el barrido de pendientes le
    ponía al XML —y al QR— una fecha que la venta nunca tuvo."""
    _empresa, _venta, comprobante = _venta_pagada(session)
    comprobante.created_at = datetime.now(UTC) - timedelta(days=3)
    session.flush()

    documento = comprobantes.documento_de(session, comprobante)
    esperada = comprobantes.fecha_emision(comprobante).date()
    assert documento.fecha_emision.date() == esperada
    assert esperada < datetime.now(UTC).date()


def test_la_fecha_se_lee_en_hora_del_negocio_y_no_en_utc(session) -> None:
    """Una venta de las 20:00 en Tarapoto es del día 25 aunque en UTC ya sea
    26. Es la misma trampa que documenta `shared.fechas`."""
    _empresa, _venta, comprobante = _venta_pagada(session)
    comprobante.created_at = datetime(2026, 8, 26, 1, 30, tzinfo=UTC)
    session.flush()

    assert comprobantes.fecha_emision(comprobante).date() == datetime(
        2026, 8, 25
    ).date()
