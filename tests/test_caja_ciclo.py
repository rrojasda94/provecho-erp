"""Ciclo de caja completo (ADR-025): conteo por denominación, relevo firmado
con PIN, POS de tarjeta, cadena de custodia, corrección de un cierre y el
candado que impide cobrar sin turno abierto.

Reusa el entorno de `test_dashboard_caja` (empresa real sembrada, punto de
venta, producto con precio, cajero y encargado): armar un segundo fixture
idéntico solo agregaría 150 líneas que envejecen en paralelo.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select

from src.modules.accounting.infrastructure.models import CierreCaja, PosTarjeta
from tests.conftest import billetes
from tests.test_dashboard_caja import (  # noqa: F401
    _abrir_caja,
    _autorizacion,
    _cerrar_caja,
    _token,
    _vender_y_cobrar,
    env,
)


# --- Conteo por denominación (RN-POS-003/007) ---------------------------------
def test_apertura_calcula_la_diferencia_contra_lo_declarado(env):
    """El encargado dice entregar 100, el cajero cuenta 90: la diferencia la
    calcula el servidor y la caja **abre igual** (RN-POS-011/012)."""
    client, ids, _ = env
    r = _abrir_caja(client, _token(client), ids, monto="90.00", declarado="100.00")
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["monto_apertura"]) == Decimal("90.00")
    assert Decimal(body["diferencia_reportada"]) == Decimal("-10.00")


def test_apertura_con_denominacion_inexistente_falla(env):
    client, ids, _ = env
    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_token(client),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "37.00",
            # No existe un billete de 37 soles.
            "detalle_denominaciones": {"37": 1},
            "autorizacion": _autorizacion(client, "accounting.caja_relevar"),
        },
    )
    assert r.status_code == 409
    assert "curso legal" in r.json()["detail"]


def test_cierre_toma_el_monto_del_conteo_no_de_un_numero_tipeado(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    cierre = _cerrar_caja(client, h, apertura["id"], "100.00").json()
    assert cierre["montos_esperados"]["esperado"] == "100.00"
    assert Decimal(cierre["descuadre_monto"]) == 0


# --- Relevo autenticado (RN-MDP-002) ------------------------------------------
def test_abrir_sin_autorizacion_del_encargado_falla(env):
    client, ids, _ = env
    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_token(client),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "autorizacion": "no-es-un-token",
        },
    )
    assert r.status_code == 403


def test_el_cajero_no_puede_relevarse_a_si_mismo(env):
    """Un relevo de uno solo no es un relevo: si el mismo usuario entrega y
    recibe, la cadena de custodia no prueba nada."""
    client, ids, _ = env
    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_token(client, username="encargado1", pin="222222"),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "autorizacion": _autorizacion(client, "accounting.caja_relevar"),
        },
    )
    assert r.status_code == 409


def test_una_autorizacion_de_otra_accion_no_sirve_para_relevar(env):
    """La elevación está acotada al permiso que se pidió: la de retirar
    efectivo no abre la caja."""
    client, ids, _ = env
    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_token(client),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "autorizacion": _autorizacion(client, "accounting.caja_retirar"),
        },
    )
    assert r.status_code == 403


# --- POS de tarjeta (RN-POS-009/010/011) --------------------------------------
def _crear_pos(client, headers, ids, serie="POS-001", emergencia=False, sucursal=True):
    return client.post(
        "/api/v1/accounting/pos-tarjeta",
        headers=headers,
        json={
            "serie": serie,
            "codigo_comercio": "12345678",
            "empresa_id": ids["empresa_id"],
            "sucursal_id": ids["sucursal_id"] if sucursal else None,
            "operador": "Izipay",
            "es_emergencia": emergencia,
        },
    )


def test_listado_de_pos_incluye_el_de_emergencia_del_pool(env):
    """El terminal de reserva no cuelga de ninguna sucursal (RN-POS-009) y
    aun así tiene que verse desde la que lo va a pedir."""
    client, ids, _ = env
    h = _token(client)
    assert _crear_pos(client, h, ids).status_code == 201
    assert _crear_pos(
        client, h, ids, serie="POS-SOS", emergencia=True, sucursal=False
    ).status_code == 201

    r = client.get(
        f"/api/v1/accounting/pos-tarjeta?sucursal_id={ids['sucursal_id']}", headers=h
    )
    assert r.status_code == 200
    series = {p["serie"] for p in r.json()}
    assert series == {"POS-001", "POS-SOS"}


def test_serie_de_pos_duplicada_falla(env):
    client, ids, _ = env
    h = _token(client)
    assert _crear_pos(client, h, ids).status_code == 201
    assert _crear_pos(client, h, ids).status_code == 409


def test_un_pos_averiado_no_impide_abrir_la_caja(env):
    """RN-POS-011: el local abre en su horario; el POS roto queda marcado y
    reportado, no bloquea la venta."""
    client, ids, TestSession = env
    h = _token(client)
    pos_id = _crear_pos(client, h, ids).json()["id"]

    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "autorizacion": _autorizacion(client, "accounting.caja_relevar"),
            "pos_verificados": [
                {
                    "pos_tarjeta_id": pos_id,
                    "operativo": False,
                    "observacion": "no imprime",
                }
            ],
        },
    )
    assert r.status_code == 201
    assert r.json()["pos_verificados"][0]["operativo"] is False
    with TestSession() as s:
        pos = s.scalar(select(PosTarjeta).where(PosTarjeta.id == uuid.UUID(pos_id)))
        assert pos.estado == "averiado"


# --- Cadena de custodia (RN-MDP-002/006) --------------------------------------
def test_el_cierre_deja_el_efectivo_en_custodia_del_encargado(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")

    r = client.get(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/custodia", headers=h
    )
    assert r.status_code == 200
    custodia = r.json()
    assert custodia["estado"] == "en_supervisor"
    assert custodia["responsable_actual_id"] == ids["encargado_id"]
    assert Decimal(custodia["monto"]) == Decimal("100.00")


def test_la_custodia_avanza_hasta_disponible_y_no_salta_tramos(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = client.get(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/custodia", headers=h
    ).json()["id"]

    def entregar(estado):
        return client.post(
            f"/api/v1/accounting/cajas/custodias/{custodia_id}/entregar",
            headers=h,
            json={
                "estado_siguiente": estado,
                "autorizacion": _autorizacion(client, "accounting.caja_relevar"),
            },
        )

    assert entregar("en_contabilidad").json()["estado"] == "en_contabilidad"
    # Volver atrás no es una transición: el efectivo ya cambió de manos.
    assert entregar("en_supervisor").status_code == 409
    r = entregar("disponible")
    assert r.status_code == 200
    assert len(r.json()["timestamps_relevo"]) == 3


# --- Corrección de un cierre (RN-MDP-005) -------------------------------------
def test_un_cierre_con_faltante_se_reabre_recuenta_y_deja_historial(env):
    client, ids, TestSession = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    cierre = _cerrar_caja(
        client, h, apertura["id"], "90.00", descuadre_atribucion="cajero"
    ).json()
    assert cierre["estado"] == "con_irregularidad"

    r = client.post(
        f"/api/v1/accounting/cajas/cierres/{cierre['id']}/reabrir",
        headers=h,
        json={
            "motivo": "aparecieron 10 soles debajo del cajón",
            "autorizacion": _autorizacion(client, "accounting.caja_reabrir"),
        },
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "en_proceso"

    recierre = _cerrar_caja(client, h, apertura["id"], "100.00").json()
    assert recierre["id"] == cierre["id"]  # un turno, un cierre
    assert recierre["estado"] == "conforme"
    assert Decimal(recierre["descuadre_monto"]) == 0
    # El faltante anterior no se borra: queda por qué y quién lo autorizó.
    assert recierre["correcciones"][0]["descuadre_anterior"] == "-10.00"
    with TestSession() as s:
        cierres = s.scalars(
            select(CierreCaja).where(
                CierreCaja.apertura_caja_id == uuid.UUID(apertura["id"])
            )
        ).all()
        assert len(cierres) == 1


def test_no_se_reabre_un_cierre_cuyo_efectivo_ya_esta_en_contabilidad(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    cierre = _cerrar_caja(client, h, apertura["id"], "90.00").json()
    custodia_id = client.get(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/custodia", headers=h
    ).json()["id"]
    client.post(
        f"/api/v1/accounting/cajas/custodias/{custodia_id}/entregar",
        headers=h,
        json={
            "estado_siguiente": "en_contabilidad",
            "autorizacion": _autorizacion(client, "accounting.caja_relevar"),
        },
    )

    r = client.post(
        f"/api/v1/accounting/cajas/cierres/{cierre['id']}/reabrir",
        headers=h,
        json={
            "motivo": "quieren recontar el cajón",
            "autorizacion": _autorizacion(client, "accounting.caja_reabrir"),
        },
    )
    assert r.status_code == 409


# --- Enlace caja ↔ venta -------------------------------------------------------
def _crear_venta(client, headers, ids, key):
    return client.post(
        "/api/v1/sales/ventas",
        headers=headers,
        json={
            "sucursal_id": ids["sucursal_id"],
            "punto_venta_id": ids["pv_id"],
            "canal": "pdv",
            "modalidad": "takeout",
            "idempotency_key": f"venta-{key}",
            "items": [{"producto_comercial_id": ids["producto_id"], "cantidad": "1"}],
        },
    ).json()


def test_no_se_cobra_sin_caja_abierta(env):
    """La plata cobrada fuera de un turno no la espera ningún cierre: el
    faltante aparece recién en contabilidad y ya no tiene responsable."""
    client, ids, _ = env
    h = _token(client)
    venta = _crear_venta(client, h, ids, "sin-caja")
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/pagos",
        headers=h,
        json={
            "medio_pago_id": ids["medio_id"],
            "monto": "50.00",
            "idempotency_key": "pago-sin-caja",
        },
    )
    assert r.status_code == 409
    assert "caja abierta" in r.json()["detail"]


def test_con_la_caja_abierta_el_cobro_pasa(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_caja(client, h, ids, monto="100.00")
    venta = _crear_venta(client, h, ids, "con-caja")
    r = client.post(
        f"/api/v1/sales/ventas/{venta['id']}/pagos",
        headers=h,
        json={
            "medio_pago_id": ids["medio_id"],
            "monto": "50.00",
            "idempotency_key": "pago-con-caja",
        },
    )
    assert r.status_code == 201


def test_el_esperado_del_arqueo_descuenta_los_retiros(env):
    """Un retiro autorizado baja el efectivo esperado: si no, el arqueo
    reporta un faltante que no existe (RN-MDP-007)."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/movimientos",
        headers=h,
        json={
            "tipo": "retiro",
            "monto": "40.00",
            "motivo": "pago al repartidor",
            "idempotency_key": "mov-retiro-0001",
            "autorizacion": _autorizacion(client, "accounting.caja_retirar"),
        },
    )
    r = client.post(
        "/api/v1/accounting/arqueos",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "tipo": "sorpresa",
            "monto_contado": "60.00",
        },
    )
    assert r.status_code == 201
    assert Decimal(r.json()["monto_esperado"]) == Decimal("60.00")
    assert Decimal(r.json()["diferencia"]) == 0
