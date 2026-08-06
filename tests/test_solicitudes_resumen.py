"""Contrato público `inventory` → `purchases`: qué artículo pide más cada
sucursal, para negociar volumen con proveedores (ver
docs/architecture/events.md). Reusa el fixture `env` de
test_transferencias.py — mismo ciclo de abastecimiento interno (ADR-020).
"""

from tests.test_transferencias import _solicitar, _token
from tests.test_transferencias import env as env  # noqa: F401,PLC0414


def test_resumen_suma_por_articulo_y_excluye_canceladas(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)

    sol1 = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "10"},
    ]).json()
    sol2 = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "5"},
    ]).json()
    # Cancelada: no debe sumar a la demanda.
    sol_cancelada = _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "100"},
    ]).json()
    r = client.post(
        f"/api/v1/inventory/solicitudes/{sol_cancelada['id']}/cancelar",
        headers=h_alm,
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/v1/inventory/solicitudes/resumen", headers=h_admin)
    assert r.status_code == 200, r.text
    filas = r.json()
    fila = next(f for f in filas if f["articulo_nombre"] == "Servilleta")
    assert float(fila["cantidad_total"]) == 15
    assert fila["num_solicitudes"] == 2
    assert sol1["id"] and sol2["id"]  # ambas contaron, la cancelada no


def test_resumen_exige_permiso(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    _solicitar(client, h_alm, ids).json()

    r = client.get("/api/v1/inventory/solicitudes/resumen", headers=h_alm)
    assert r.status_code == 403


def test_resumen_filtra_por_rango_de_fecha(env):
    client, ids, _ = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    _solicitar(client, h_alm, ids, [
        {"sku_id": ids["sku_servilleta"], "cantidad": "10"},
    ])

    r = client.get(
        "/api/v1/inventory/solicitudes/resumen?desde=2099-01-01",
        headers=h_admin,
    )
    assert r.status_code == 200, r.text
    assert r.json() == []
