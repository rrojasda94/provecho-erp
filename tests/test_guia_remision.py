"""Guía de remisión de un traslado entre almacenes (RN-GDR-001..003,
RN-TRP-002).

Reusa el entorno de `test_transferencias` (empresa sembrada, almacén central
y dos locales, artículos con y sin lote, almacenero con su rol): armar un
segundo fixture idéntico solo agregaría 120 líneas que envejecen en
paralelo.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.modules.inventory.infrastructure.models import GuiaRemision
from src.shared.integrations.factiliza import guias as guias_mapper
from tests.test_transferencias import (  # noqa: F401
    _crear_lote,
    _ingresar,
    _token,
    env,
)

GUIA = {
    "chofer_nombres": "Luis",
    "chofer_apellidos": "Ramírez Vela",
    "chofer_num_doc": "44556677",
    "chofer_licencia": "Q44556677",
    "vehiculo_placa": "ABC-123",
    "peso_bruto_kg": "12.500",
}


def _despachar(client, h, ids, items, transferencia_kwargs=None):
    r = client.post(
        "/api/v1/inventory/transferencias",
        headers=h,
        json={
            "origen_almacen_id": ids["central_id"],
            "destino_almacen_id": ids["local_id"],
            "items": items,
            **(transferencia_kwargs or {}),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _emitir(client, h, transferencia_id, **extra):
    return client.post(
        f"/api/v1/inventory/transferencias/{transferencia_id}/guia",
        headers=h,
        json={**GUIA, **extra},
    )


@pytest.fixture()
def traslado(env):  # noqa: F811
    """Un traslado ya despachado, listo para que le emitan la guía."""
    client, ids, TestSession = env
    h = _token(client)
    _ingresar(client, h, ids["central_id"], ids["sku_servilleta"], 100)
    transferencia = _despachar(
        client, h, ids, [{"sku_id": ids["sku_servilleta"], "cantidad": "10"}]
    )
    return client, ids, TestSession, h, transferencia


def test_la_guia_declara_lo_que_salio_del_origen(traslado):
    """RN-TRP-002: lo transportado coincide con lo declarado. Las líneas no
    se teclean — salen de la transferencia."""
    client, _, _, h, transferencia = traslado

    r = _emitir(client, h, transferencia["id"])
    assert r.status_code == 201, r.text
    guia = r.json()

    assert len(guia["items"]) == 1
    assert Decimal(guia["items"][0]["cantidad"]) == Decimal("10")
    assert guia["items"][0]["descripcion"] == "Servilleta"
    assert guia["serie"] == "T001"
    assert guia["correlativo"] == 1
    assert guia["transferencia_id"] == transferencia["id"]


def test_la_guia_congela_origen_destino_y_rucs(traslado):
    """RN-GDR-001. En un traslado entre establecimientos propios el RUC del
    emisor y el del receptor son el mismo, y que coincidan es lo que
    sustenta el motivo `04`."""
    client, _, _, h, transferencia = traslado

    guia = _emitir(client, h, transferencia["id"]).json()

    assert guia["motivo_traslado"] == "04"
    assert guia["ruc_emisor"] == guia["ruc_receptor"]
    assert guia["lugar_origen"] and guia["lugar_destino"]
    assert guia["lugar_origen"] != guia["lugar_destino"]
    assert guia["vehiculo_placa"] == "ABC-123"


def test_un_traslado_una_guia(traslado):
    """Reemitir sobre la misma transferencia devuelve la misma guía: dos
    guías del mismo traslado declararían la misma mercadería dos veces."""
    client, _, TestSession, h, transferencia = traslado

    primera = _emitir(client, h, transferencia["id"]).json()
    segunda = _emitir(client, h, transferencia["id"]).json()

    assert primera["id"] == segunda["id"]
    assert primera["correlativo"] == segunda["correlativo"]
    with TestSession() as s:
        assert len(list(s.scalars(select(GuiaRemision)))) == 1


def test_el_correlativo_avanza_por_empresa_y_serie(traslado):
    client, ids, _, h, transferencia = traslado
    otra = _despachar(
        client, h, ids, [{"sku_id": ids["sku_servilleta"], "cantidad": "5"}]
    )

    primera = _emitir(client, h, transferencia["id"]).json()
    segunda = _emitir(client, h, otra["id"]).json()

    assert (primera["correlativo"], segunda["correlativo"]) == (1, 2)


def test_las_lineas_se_agrupan_por_sku_aunque_salgan_de_varios_lotes(env):  # noqa: F811
    """El despacho reparte por FEFO y una línea puede salir de tres lotes
    (ADR-015). SUNAT declara producto y cantidad: la guía trae **una** línea
    por SKU, y la trazabilidad por lote sigue en `transferencia_item`."""
    client, ids, _ = env
    h = _token(client)
    lote_viejo = _crear_lote(client, h, ids, "L-VIEJO", "2026-09-01")
    lote_nuevo = _crear_lote(client, h, ids, "L-NUEVO", "2026-12-01")
    _ingresar(client, h, ids["central_id"], ids["sku_queso"], 4, lote_viejo)
    _ingresar(client, h, ids["central_id"], ids["sku_queso"], 10, lote_nuevo)

    transferencia = _despachar(
        client, h, ids, [{"sku_id": ids["sku_queso"], "cantidad": "6"}]
    )
    detalle = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}", headers=h
    ).json()
    # Dos lotes tocados en la transferencia...
    assert len(detalle["items"]) == 2

    guia = _emitir(client, h, transferencia["id"]).json()
    # ...y una sola línea en la guía, por la cantidad total.
    assert len(guia["items"]) == 1
    assert Decimal(guia["items"][0]["cantidad"]) == Decimal("6")
    # Kilo → KGM del catálogo 03 de SUNAT.
    assert guia["items"][0]["unidad"] == "KGM"


def test_la_guia_nace_pendiente_de_sunat(traslado):
    """La guía impresa es la que viaja: existe apenas se emite, y que SUNAT
    la acepte llega después por la cola (ADR-005)."""
    client, _, _, h, transferencia = traslado
    assert _emitir(client, h, transferencia["id"]).json()["estado_emision"] == "pendiente"


def test_peso_bruto_en_cero_se_rechaza(traslado):
    client, _, _, h, transferencia = traslado
    r = _emitir(client, h, transferencia["id"], peso_bruto_kg="0")
    assert r.status_code == 422


def test_motivo_fuera_del_catalogo_20_se_rechaza(traslado):
    client, _, _, h, transferencia = traslado
    r = _emitir(client, h, transferencia["id"], motivo_traslado="99")
    assert r.status_code == 422


def test_sin_permiso_de_almacen_no_se_emite(traslado):
    """RN-GDR-002: la emite el área de almacén. El cajero tiene
    `inventory.leer` y no puede emitir."""
    client, _, TestSession, _, transferencia = traslado
    from sqlalchemy import select as _select

    from src.modules.users.infrastructure.models import (
        Rol,
        Usuario,
        UsuarioRol,
    )
    from src.modules.users.infrastructure.security import hash_pin

    with TestSession() as s:
        cajero = Usuario(username="cajero1", pin_hash=hash_pin("111111"), tipo="humano")
        s.add(cajero)
        s.flush()
        rol = s.scalar(_select(Rol).where(Rol.nombre == "cajero"))
        s.add(UsuarioRol(usuario_id=cajero.id, rol_id=rol.id))
        s.commit()

    h_cajero = _token(client, "cajero1", "111111")
    assert _emitir(client, h_cajero, transferencia["id"]).status_code == 403


def test_guia_de_transferencia_inexistente_404(env):  # noqa: F811
    client, _, _ = env
    h = _token(client)
    r = _emitir(client, h, str(uuid.uuid4()))
    assert r.status_code == 404


def test_leer_la_guia_antes_de_emitirla_404(traslado):
    client, _, _, h, transferencia = traslado
    r = client.get(
        f"/api/v1/inventory/transferencias/{transferencia['id']}/guia", headers=h
    )
    assert r.status_code == 404


def test_listado_de_guias_pagina(traslado):
    client, _, _, h, transferencia = traslado
    _emitir(client, h, transferencia["id"])

    body = client.get("/api/v1/inventory/guias-remision", headers=h).json()
    assert body["total"] == 1
    assert body["items"][0]["serie"] == "T001"


# --- Mapper de Factiliza ------------------------------------------------------
def test_unidad_sin_mapear_cae_en_niu():
    """El catálogo 03 de SUNAT tiene cientos de unidades y adivinar las que
    faltan sería peor que el fallback: `NIU` es lo que SUNAT espera de un
    bien contable por piezas."""
    assert guias_mapper.codigo_unidad("Kilo") == "KGM"
    assert guias_mapper.codigo_unidad("Litro") == "LTR"
    assert guias_mapper.codigo_unidad("Bandeja de tres") == "NIU"
    assert guias_mapper.codigo_unidad("") == "NIU"


def test_el_payload_no_lleva_aritmetica_tributaria():
    """Una guía no cobra nada: no declara valor de venta, IGV ni forma de
    pago. Que el payload no los traiga es lo que impide reusar el cálculo de
    la factura sobre un documento que no lo tiene."""
    import datetime

    payload = guias_mapper.construir_payload_guia(
        guias_mapper.Guia(
            empresa_ruc="20450311520",
            serie="T001",
            correlativo=7,
            fecha_emision=datetime.datetime(2026, 8, 5, 10, 0),
            fecha_inicio_traslado=datetime.date(2026, 8, 5),
            motivo_traslado="04",
            modalidad_traslado="02",
            peso_bruto_kg=Decimal("12.5"),
            receptor_ruc="20450311520",
            lugar_origen="Jr. Ramón Castilla 248",
            lugar_destino="Jr. Lamas 299",
            chofer_nombres="Luis",
            chofer_apellidos="Ramírez",
            chofer_num_doc="44556677",
            chofer_licencia="Q44556677",
            vehiculo_placa="ABC-123",
            items=[
                guias_mapper.ItemGuia(
                    codigo="SKU-1",
                    descripcion="Servilleta",
                    cantidad=Decimal("10"),
                    unidad="NIU",
                )
            ],
        )
    )

    assert payload["tipo_Doc"] == "09"
    assert payload["cod_Traslado"] == "04"
    assert payload["peso_Total"] == 12.5
    assert payload["detalle"][0]["cantidad"] == 10.0
    for campo in ("monto_Igv", "valor_Venta", "forma_pago", "monto_Imp_Venta"):
        assert campo not in payload
