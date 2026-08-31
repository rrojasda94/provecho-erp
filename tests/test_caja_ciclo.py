"""Ciclo de caja completo (ADR-025, enmendado por ADR-049): conteo por
denominación, POS de tarjeta, cadena de custodia firmada con PIN, corrección
de un cierre y el candado que impide cobrar sin turno abierto.

La línea que separa los dos grupos de casos de acá: **abrir y cerrar los
hace el cajero solo** (RN-MDP-008) y **entregar el efectivo lo firma quien
recibe** (RN-MDP-002). Un test que exija PIN para abrir estaría probando la
regla vieja.

Reusa el entorno de `test_dashboard_caja` (empresa real sembrada, punto de
venta, producto con precio, cajero y encargado): armar un segundo fixture
idéntico solo agregaría 150 líneas que envejecen en paralelo.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select

from src.modules.accounting.infrastructure.models import CierreCaja, PosTarjeta
from src.modules.users.infrastructure.models import Usuario, UsuarioSucursal
from src.modules.users.infrastructure.security import hash_pin
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


# --- El turno lo opera el cajero solo (RN-MDP-008) ----------------------------
def _cajero(client):
    """Sesión del cajero de verdad, con su rol y nada más.

    Los demás casos entran como `admin` por comodidad, pero acá el rol **es**
    lo que se prueba: `cajero` tiene `accounting.caja_operar` y no tiene
    `accounting.caja_relevar`.
    """
    return _token(client, username="cajero_test", pin="111111")


def test_el_cajero_abre_su_turno_sin_firma_de_nadie(env):
    """Lo que prueba cuánto había en el cajón es el conteo, no una firma.

    Exigir el PIN de un encargado para abrir no protegía el efectivo y sí
    obligaba a ir a buscarlo cada mañana — que en el local se resolvía
    dejando la sesión del encargado abierta en la caja.
    """
    client, ids, _ = env
    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_cajero(client),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cajero_id"] == ids["cajero_id"]
    # Nadie firmó: inventar una contraparte sería peor que decir que no hubo.
    assert body["relevo_encargado_id"] is None


def test_el_cajero_cierra_su_turno_sin_firma_de_nadie(env):
    client, ids, _ = env
    h = _cajero(client)
    apertura = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
        },
    ).json()
    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={
            "detalle_denominaciones": billetes("100.00"),
            "custodia": "local_caja_fuerte",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "conforme"


def test_sin_caja_operar_no_se_abre_la_caja(env):
    """Sacar la elevación no dejó el endpoint abierto: el permiso de sesión
    sigue siendo el candado, y ahora es el único."""
    client, ids, TestSession = env
    with TestSession() as s:
        # Con sucursal —si no, el JWT sale sin `empresa_id` y el 403 vendría
        # del tenant— y sin un solo rol, que es lo que se quiere probar.
        usuario = Usuario(
            username="sinpermisos", pin_hash=hash_pin("999999"), tipo="humano"
        )
        s.add(usuario)
        s.flush()
        s.add(
            UsuarioSucursal(
                usuario_id=usuario.id, sucursal_id=uuid.UUID(ids["sucursal_id"])
            )
        )
        s.commit()

    r = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=_token(client, username="sinpermisos", pin="999999"),
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
        },
    )
    assert r.status_code == 403


# --- Relevo autenticado del efectivo (RN-MDP-002) -----------------------------
def _entregar(client, headers, custodia_id, estado, autorizacion):
    return client.post(
        f"/api/v1/accounting/cajas/custodias/{custodia_id}/entregar",
        headers=headers,
        json={"estado_siguiente": estado, "autorizacion": autorizacion},
    )


def _custodia_de(client, headers, apertura_id):
    """Estado del efectivo del turno.

    Leer la custodia exige `accounting.leer`, que el rol `cajero` no tiene:
    los casos que operan como cajero pasan acá las cabeceras del `admin`
    para mirar el resultado. Es una lectura de verificación, no parte del
    flujo que se prueba.
    """
    r = client.get(
        f"/api/v1/accounting/cajas/apertura/{apertura_id}/custodia", headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_entregar_sin_autorizacion_de_quien_recibe_falla(env):
    """Acá sí hay una entrega de efectivo, y sin firma no prueba nada."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = _custodia_de(client, h, apertura["id"])["id"]

    assert _entregar(
        client, h, custodia_id, "en_supervisor", "no-es-un-token"
    ).status_code == 403


def test_una_autorizacion_de_otra_accion_no_sirve_para_relevar(env):
    """La elevación está acotada al permiso que se pidió: la de retirar
    efectivo no sirve para recibirlo."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = _custodia_de(client, h, apertura["id"])["id"]

    r = _entregar(
        client,
        h,
        custodia_id,
        "en_supervisor",
        _autorizacion(client, "accounting.caja_retirar"),
    )
    assert r.status_code == 403


def test_el_cajero_no_puede_firmar_que_recibio_su_propio_efectivo(env):
    """El cajero cierra solo, pero **no** se entrega la plata a sí mismo.

    Es la segregación que sobrevive: `accounting.caja_relevar` no está en su
    rol, así que la elevación con su PIN se rechaza aunque tenga la pantalla
    abierta con su propia sesión.
    """
    client, ids, _ = env
    h, lector = _cajero(client), _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = _custodia_de(client, lector, apertura["id"])["id"]

    elevacion = client.post(
        "/api/v1/auth/autorizar",
        json={
            "username": "cajero_test",
            "pin": "111111",
            "permiso": "accounting.caja_relevar",
        },
    )
    # 401 y no 403: `POST /auth/autorizar` no distingue "PIN equivocado" de
    # "no tenés el permiso" — decirlo sería confirmarle a cualquiera qué
    # puede hacer cada usuario del local a fuerza de probar.
    assert elevacion.status_code == 401, elevacion.text
    # Sin elevación no hay token que mandar, y el tramo no avanza: la plata
    # sigue en su cajón, a su nombre.
    assert _entregar(
        client, h, custodia_id, "en_supervisor", "sin-firma"
    ).status_code == 403
    assert _custodia_de(client, lector, apertura["id"])["estado"] == "en_caja"



# --- La elevación es de un solo uso (RN-AUD-005) ------------------------------
def _retirar(client, h, apertura_id, token, idempotency_key, monto="10.00"):
    return client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura_id}/movimientos",
        headers=h,
        json={
            "tipo": "retiro",
            "monto": monto,
            "motivo": "pago al repartidor",
            "idempotency_key": idempotency_key,
            "autorizacion": token,
        },
    )


def test_una_autorizacion_no_sirve_para_dos_retiros(env):
    """Una elevación, una operación.

    Sin esto, el cajero conseguía la firma del supervisor para un retiro y
    la reusaba durante los tres minutos siguientes: el rastro se los
    atribuía todos al supervisor, que es justo lo que la elevación existe
    para evitar.
    """
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    token = _autorizacion(client, "accounting.caja_retirar")

    assert _retirar(client, h, apertura["id"], token, "mov-uso-1").status_code == 201
    segundo = _retirar(client, h, apertura["id"], token, "mov-uso-2")
    assert segundo.status_code == 403
    assert "ya fue usada" in segundo.json()["detail"]


def test_el_reintento_del_mismo_retiro_no_cuenta_como_reuso(env):
    """Un timeout de red no puede obligar al supervisor a volver al
    mostrador: mismo `idempotency_key`, misma operación."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    token = _autorizacion(client, "accounting.caja_retirar")

    primero = _retirar(client, h, apertura["id"], token, "mov-reintento")
    reintento = _retirar(client, h, apertura["id"], token, "mov-reintento")
    assert primero.status_code == 201
    assert reintento.status_code == 201
    # Y no se retiró dos veces: la idempotencia devuelve el mismo movimiento.
    assert reintento.json()["id"] == primero.json()["id"]


def test_con_redis_caido_la_autorizacion_sigue_valiendo(env, monkeypatch):
    """Fail-open declarado: sin Redis no hay anti-replay, pero el
    restaurante sigue operando (mismo criterio que el rate limit)."""
    import redis

    from src.core import rate_limit

    class _Caido:
        def set(self, *a, **k):
            raise redis.RedisError("sin conexión")

        def get(self, *a, **k):
            raise redis.RedisError("sin conexión")

        def incr(self, *a, **k):
            raise redis.RedisError("sin conexión")

        def expire(self, *a, **k):
            raise redis.RedisError("sin conexión")

    monkeypatch.setattr(rate_limit, "_client", _Caido())
    monkeypatch.setattr(rate_limit, "_reintentar_desde", 0.0)
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    token = _autorizacion(client, "accounting.caja_retirar")

    assert _retirar(client, h, apertura["id"], token, "mov-caido").status_code == 201


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


# --- Cadena de custodia (RN-MDP-002/006/008) ----------------------------------
def test_el_cierre_deja_el_efectivo_en_el_cajon_a_nombre_del_cajero(env):
    """El cierre es un conteo, no una entrega.

    Nacer en `en_supervisor` daría por recibida plata que sigue en el cajón,
    y un faltante detectado después quedaría a nombre de alguien que nunca la
    tocó.
    """
    client, ids, _ = env
    h, lector = _cajero(client), _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")

    custodia = _custodia_de(client, lector, apertura["id"])
    assert custodia["estado"] == "en_caja"
    assert custodia["responsable_actual_id"] == ids["cajero_id"]
    assert Decimal(custodia["monto"]) == Decimal("100.00")
    assert custodia["timestamps_relevo"][0]["usuario_id"] == ids["cajero_id"]


def test_el_encargado_recibe_el_efectivo_del_cajon_y_queda_firmado(env):
    """El tramo nuevo: `en_caja → en_supervisor`. Lo firma quien recibe, y
    el registro dice quién y cuándo — sin eso, un turno de hace tres días no
    dice en manos de quién quedó la plata."""
    client, ids, _ = env
    h, lector = _cajero(client), _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = _custodia_de(client, lector, apertura["id"])["id"]

    # La pantalla la opera quien tenga `caja_operar` —acá, el propio cajero—
    # y quien firma es otro: el encargado pone su PIN sobre ese terminal.
    r = _entregar(
        client,
        h,
        custodia_id,
        "en_supervisor",
        _autorizacion(client, "accounting.caja_relevar"),
    )
    assert r.status_code == 200, r.text
    custodia = r.json()
    assert custodia["estado"] == "en_supervisor"
    assert custodia["responsable_actual_id"] == ids["encargado_id"]
    firma = custodia["timestamps_relevo"][-1]
    assert firma["usuario_id"] == ids["encargado_id"]
    assert firma["rol"] == "en_supervisor"
    assert firma["timestamp"]


def test_la_custodia_avanza_hasta_disponible_y_no_salta_tramos(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "100.00")
    custodia_id = _custodia_de(client, h, apertura["id"])["id"]

    def entregar(estado):
        return _entregar(
            client,
            h,
            custodia_id,
            estado,
            _autorizacion(client, "accounting.caja_relevar"),
        )

    # Desde el cajón no se salta a contabilidad: el encargado es un eslabón,
    # no un trámite.
    assert entregar("en_contabilidad").status_code == 409
    assert entregar("en_supervisor").json()["estado"] == "en_supervisor"
    assert entregar("en_contabilidad").json()["estado"] == "en_contabilidad"
    # Volver atrás no es una transición: el efectivo ya cambió de manos.
    assert entregar("en_supervisor").status_code == 409
    r = entregar("disponible")
    assert r.status_code == 200
    # Cuatro firmas: el cajero al cerrar, más los tres tramos entregados.
    assert len(r.json()["timestamps_relevo"]) == 4


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


def test_un_cierre_se_recuenta_mientras_la_plata_siga_en_el_cajon(env):
    """El caso que antes no existía: recién cerrado, el efectivo ya estaba
    `en_supervisor`. Ahora sigue `en_caja` y recontarlo prueba algo."""
    client, ids, _ = env
    h, lector = _cajero(client), _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    cierre = _cerrar_caja(client, h, apertura["id"], "90.00").json()
    assert _custodia_de(client, lector, apertura["id"])["estado"] == "en_caja"

    r = client.post(
        f"/api/v1/accounting/cajas/cierres/{cierre['id']}/reabrir",
        headers=h,
        json={
            "motivo": "el cajero no había contado el fondo del segundo cajón",
            "autorizacion": _autorizacion(client, "accounting.caja_reabrir"),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_proceso"


def test_no_se_reabre_un_cierre_cuyo_efectivo_ya_esta_en_contabilidad(env):
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    cierre = _cerrar_caja(client, h, apertura["id"], "90.00").json()
    custodia_id = _custodia_de(client, h, apertura["id"])["id"]
    # Dos tramos: la plata sale del cajón y recién después viaja a
    # contabilidad. Es a partir de ahí que recontar el cajón no prueba nada.
    for estado in ("en_supervisor", "en_contabilidad"):
        assert _entregar(
            client,
            h,
            custodia_id,
            estado,
            _autorizacion(client, "accounting.caja_relevar"),
        ).status_code == 200

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


# --- Cuadre de tarjetas al cierre (RN-POS-004) --------------------------------
def test_el_cierre_exige_el_lote_de_cada_pos_operativo(env):
    """Cerrar cuadrando solo el cajón deja la mitad del turno sin verificar:
    un cobro mal pasado en el POS aparecería recién en la liquidación."""
    client, ids, _ = env
    h = _token(client)
    pos_id = _crear_pos(client, h, ids).json()["id"]
    apertura = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "pos_verificados": [{"pos_tarjeta_id": pos_id, "operativo": True}],
        },
    ).json()

    r = _cerrar_caja(client, h, apertura["id"], "100.00")
    assert r.status_code == 409
    assert "reporte de lote" in r.json()["detail"]

    ok = _cerrar_caja(
        client,
        h,
        apertura["id"],
        "100.00",
        reportes_pos=[{"pos_tarjeta_id": pos_id, "monto_lote": "0.00"}],
    )
    assert ok.status_code == 200
    assert ok.json()["estado"] == "conforme"


def test_un_pos_averiado_no_debe_reporte(env):
    """No cobró nada: exigirle el lote sería trabar el cierre por un
    terminal que estuvo apagado todo el turno (RN-POS-011)."""
    client, ids, _ = env
    h = _token(client)
    pos_id = _crear_pos(client, h, ids).json()["id"]
    apertura = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "pos_verificados": [{"pos_tarjeta_id": pos_id, "operativo": False}],
        },
    ).json()

    assert _cerrar_caja(client, h, apertura["id"], "100.00").status_code == 200


def test_un_lote_que_no_cuadra_deja_el_cierre_irregular(env):
    """El cajón puede cuadrar perfecto y las tarjetas no: son dos frentes
    distintos y cualquiera de los dos marca el cierre."""
    client, ids, _ = env
    h = _token(client)
    pos_id = _crear_pos(client, h, ids).json()["id"]
    apertura = client.post(
        "/api/v1/accounting/cajas/apertura",
        headers=h,
        json={
            "punto_venta_id": ids["pv_id"],
            "monto_declarado": "100.00",
            "detalle_denominaciones": billetes("100.00"),
            "pos_verificados": [{"pos_tarjeta_id": pos_id, "operativo": True}],
        },
    ).json()

    # El terminal declara S/50 y no hubo ningún cobro con tarjeta.
    r = _cerrar_caja(
        client,
        h,
        apertura["id"],
        "100.00",
        descuadre_atribucion="cajero",
        reportes_pos=[{"pos_tarjeta_id": pos_id, "monto_lote": "50.00"}],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "con_irregularidad"
    # El descuadre del cajón sigue siendo cero: el problema está en tarjetas.
    assert Decimal(body["descuadre_monto"]) == 0
    # Comparado como Decimal: "0" y "0.00" son el mismo número.
    assert Decimal(body["montos_esperados"]["tarjeta"]) == 0


def test_sin_pos_verificados_el_cierre_no_pide_nada(env):
    """Un local sin terminales no tiene tarjetas que cuadrar."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    assert _cerrar_caja(client, h, apertura["id"], "100.00").status_code == 200


# --- Listado de turnos cerrados (pantalla de contabilidad) --------------------
def test_turnos_cerrados_traen_descuadre_y_tramo_de_custodia(env):
    """La fila con la que trabaja contabilidad: sin este listado, reabrir un
    cierre o recibir el efectivo exigía conocer de memoria el id de la
    apertura."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "90.00")

    turnos = client.get("/api/v1/accounting/cajas/turnos", headers=h).json()
    assert len(turnos) == 1
    turno = turnos[0]
    assert turno["apertura_caja_id"] == apertura["id"]
    assert Decimal(turno["descuadre_monto"]) == Decimal("-10.00")
    assert turno["estado"] == "con_irregularidad"
    # El efectivo arranca en el cajón: el tramo cajero→encargado todavía no
    # ocurrió y es justo la acción que esta pantalla ofrece.
    assert turno["custodia_estado"] == "en_caja"
    assert turno["custodia_id"] is not None
    assert turno["caja"]


def test_el_cierre_irregular_se_puede_abrir_desde_su_reporte(env):
    """Destino de `accounting.cierre_caja_irregular`. La fila del listado
    dice cuánto descuadró; el detalle dice contra qué, que es lo único con
    lo que se decide reclamar o corregir (RN-MDP-005)."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    _cerrar_caja(client, h, apertura["id"], "90.00")
    cierre_id = client.get(
        "/api/v1/accounting/cajas/turnos", headers=h
    ).json()[0]["cierre_id"]

    r = client.get(f"/api/v1/accounting/cajas/cierres/{cierre_id}", headers=h)
    assert r.status_code == 200, r.text
    detalle = r.json()
    assert detalle["cierre_id"] == cierre_id
    assert Decimal(detalle["descuadre_monto"]) == Decimal("-10.00")
    assert detalle["montos_esperados"] is not None
    assert detalle["montos_reales"] is not None
    # Quién firmó cada tramo: el reporte acusa un faltante y esto dice a
    # quién preguntarle.
    assert detalle["relevos"]

    fantasma = "00000000-0000-0000-0000-000000000000"
    assert client.get(
        f"/api/v1/accounting/cajas/cierres/{fantasma}", headers=h
    ).status_code == 404


def test_un_turno_abierto_no_aparece_entre_los_cerrados(env):
    client, ids, _ = env
    h = _token(client)
    _abrir_caja(client, h, ids, monto="100.00")
    assert client.get("/api/v1/accounting/cajas/turnos", headers=h).json() == []


def test_turnos_con_rango_invertido_400(env):
    client, _, _ = env
    h = _token(client)
    r = client.get(
        "/api/v1/accounting/cajas/turnos?desde=2026-08-05&hasta=2026-08-04", headers=h
    )
    assert r.status_code == 400


def test_atribucion_del_descuadre_fuera_del_enum_se_rechaza(env):
    """Texto libre entraba y dejaba el turno **ilegible**: la columna es un
    enum de tres valores y la lectura reventaba después con `LookupError` al
    mapear la fila. Se rechaza en el borde."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={
            "detalle_denominaciones": billetes("90.00"),
            "custodia": "Encargado de turno",
            "descuadre_atribucion": "falta un billete de 20",
        },
    )
    assert r.status_code == 422
    # Y el turno sigue siendo legible: nada se escribió.
    assert client.get("/api/v1/accounting/cajas/turnos", headers=h).json() == []


def test_destino_de_custodia_fuera_del_enum_se_rechaza(env):
    """`custodia` es a dónde va el efectivo, no el nombre de quien lo recibe
    —eso lo prueba la firma del tramo de custodia—. Un nombre tecleado
    entraba y dejaba el turno ilegible igual que la atribución del
    descuadre."""
    client, ids, _ = env
    h = _token(client)
    apertura = _abrir_caja(client, h, ids, monto="100.00").json()
    r = client.post(
        f"/api/v1/accounting/cajas/apertura/{apertura['id']}/cierre",
        headers=h,
        json={
            "detalle_denominaciones": billetes("100.00"),
            "custodia": "Juan el encargado",
        },
    )
    assert r.status_code == 422
