"""Legajo del trabajador y las dos bandejas que no caben en él.

Reusa el entorno de `test_rrhh` (empresa sembrada, persona, roles): armar
otro fixture idéntico solo agregaría líneas que envejecen en paralelo.
"""

from sqlalchemy import select

from tests.test_rrhh import _crear_trabajador, _token, env  # noqa: F401


def _trabajador(client, h, ids):
    return _crear_trabajador(client, h, ids).json()["id"]


def _contrato(client, h, trabajador_id):
    return client.post(
        "/api/v1/rrhh/contratos-laborales",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "modalidad": "indeterminado",
            "jornada_horas_semana": "48",
            "remuneracion": "1300",
            "fecha_inicio": "2026-01-01",
        },
    )


def _permiso(client, h, trabajador_id, desde="2026-08-01"):
    return client.post(
        "/api/v1/rrhh/solicitudes-permiso",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "tipo": "vacaciones",
            "fecha_desde": desde,
            "fecha_hasta": "2026-08-15",
        },
    )


def _boleta(client, h, trabajador_id):
    return client.post(
        "/api/v1/rrhh/boletas-pago",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "periodo": "2026-07",
            "dias_laborados": 30,
            "remuneracion": "1300",
            "ingresos": {"basico": "1300"},
            "descuentos": {"onp": "169"},
            "aportes_empleador": "0",
            "neto_pagar": "1131",
            "fecha_pago": "2026-08-05",
            "idempotency_key": "boleta-legajo-1",
        },
    )


def _rol_solo_lectura(TestSession, username="lector1", pin="111111"):
    """Un usuario con `rrhh.leer` y **sin** `rrhh.nomina_gestionar`: es el
    caso del supervisor, que ve las amonestaciones de su gente pero no sus
    sueldos."""
    from src.modules.users.infrastructure.models import (
        Permiso,
        Rol,
        RolPermiso,
        Sucursal,
        Usuario,
        UsuarioRol,
        UsuarioSucursal,
    )
    from src.modules.users.infrastructure.security import hash_pin

    with TestSession() as s:
        rol = Rol(nombre="rrhh_lector")
        s.add(rol)
        s.flush()
        permiso = s.scalar(select(Permiso).where(Permiso.codigo == "rrhh.leer"))
        s.add(RolPermiso(rol_id=rol.id, permiso_id=permiso.id))
        usuario = Usuario(username=username, pin_hash=hash_pin(pin), tipo="humano")
        s.add(usuario)
        s.flush()
        s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
        # Sin `usuario_sucursal` el JWT sale sin `empresa_id` y todo recurso
        # escopado responde 403 (ADR-004): el usuario existiría pero no
        # podría leer nada, y el test mediría eso en vez del permiso.
        for sucursal in s.scalars(select(Sucursal)):
            s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
        s.commit()


# --- Legajo -------------------------------------------------------------------
def test_el_legajo_trae_el_expediente_en_una_sola_lectura(env):  # noqa: F811
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _trabajador(client, h, ids)
    _contrato(client, h, trabajador_id)
    _permiso(client, h, trabajador_id)

    r = client.get(f"/api/v1/rrhh/trabajadores/{trabajador_id}/legajo", headers=h)
    assert r.status_code == 200, r.text
    legajo = r.json()
    assert legajo["trabajador"]["id"] == trabajador_id
    assert len(legajo["contratos"]) == 1
    assert len(legajo["permisos"]) == 1
    # Las listas vacías existen igual: la pantalla no tiene que adivinar si
    # la clave falta porque no hay datos o porque no la mandaron.
    assert legajo["amonestaciones"] == []
    assert legajo["certificados"] == []


def test_la_nomina_solo_viaja_con_permiso_de_nomina(env):  # noqa: F811
    """Boletas y liquidaciones llevan remuneración. Que una boleta ya fuera
    legible pidiéndola por su id no es razón para volverla navegable."""
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _trabajador(client, h, ids)
    assert _boleta(client, h, trabajador_id).status_code == 201

    # admin tiene "*", así que ve la nómina.
    como_admin = client.get(
        f"/api/v1/rrhh/trabajadores/{trabajador_id}/legajo", headers=h
    ).json()
    assert como_admin["nomina_visible"] is True
    assert len(como_admin["boletas"]) == 1

    _rol_solo_lectura(TestSession)
    h_lector = _token(client, "lector1", "111111")
    como_lector = client.get(
        f"/api/v1/rrhh/trabajadores/{trabajador_id}/legajo", headers=h_lector
    ).json()
    # Ve el expediente...
    assert como_lector["trabajador"]["id"] == trabajador_id
    # ...pero no los sueldos, y el legajo lo **dice** en vez de callarlo:
    # sin esta bandera, un legajo censurado se lee igual que uno sin boletas.
    assert como_lector["nomina_visible"] is False
    assert como_lector["boletas"] == []
    # Y tampoco por la ventana: la ficha del trabajador lleva el sueldo base.
    assert como_lector["trabajador"]["remuneracion_base"] is None


def test_la_remuneracion_no_viaja_en_el_listado_de_trabajadores(env):  # noqa: F811
    """El legajo escondía la nómina y el listado la devolvía igual: quien
    solo tiene `rrhh.leer` leía el sueldo de toda la plantilla."""
    client, ids, TestSession = env
    h = _token(client)
    trabajador_id = _crear_trabajador(
        client, h, ids, remuneracion_base="2500.00"
    ).json()["id"]

    como_admin = client.get("/api/v1/rrhh/trabajadores", headers=h).json()
    assert como_admin["items"][0]["remuneracion_base"] == "2500.00"

    _rol_solo_lectura(TestSession, "lector2", "222222")
    h_lector = _token(client, "lector2", "222222")

    listado = client.get("/api/v1/rrhh/trabajadores", headers=h_lector)
    assert listado.status_code == 200, listado.text
    assert listado.json()["items"][0]["remuneracion_base"] is None

    ficha = client.get(f"/api/v1/rrhh/trabajadores/{trabajador_id}", headers=h_lector)
    assert ficha.status_code == 200, ficha.text
    # El resto de la ficha sigue viajando: se censura el sueldo, no al
    # trabajador.
    assert ficha.json()["cargo"] == "Mozo"
    assert ficha.json()["remuneracion_base"] is None


def test_legajo_de_trabajador_inexistente_404(env):  # noqa: F811
    import uuid

    client, _, _ = env
    r = client.get(
        f"/api/v1/rrhh/trabajadores/{uuid.uuid4()}/legajo", headers=_token(client)
    )
    assert r.status_code == 404


# --- Bandeja de permisos ------------------------------------------------------
def test_la_bandeja_filtra_por_estado(env):  # noqa: F811
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _trabajador(client, h, ids)
    pendiente = _permiso(client, h, trabajador_id, "2026-09-01").json()
    aprobado = _permiso(client, h, trabajador_id, "2026-10-01").json()
    client.post(
        f"/api/v1/rrhh/solicitudes-permiso/{aprobado['id']}/aprobar", headers=h
    )

    todas = client.get("/api/v1/rrhh/solicitudes-permiso", headers=h).json()
    assert todas["total"] == 2
    solo_pendientes = client.get(
        "/api/v1/rrhh/solicitudes-permiso?estado=pendiente", headers=h
    ).json()
    assert solo_pendientes["total"] == 1
    assert solo_pendientes["items"][0]["id"] == pendiente["id"]


def test_la_bandeja_ordena_por_la_que_envejece_primero(env):  # noqa: F811
    """Una solicitud de vacaciones que espera desde hace un mes es la que hay
    que atender, no la última que entró."""
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _trabajador(client, h, ids)
    tarde = _permiso(client, h, trabajador_id, "2026-12-01").json()
    temprano = _permiso(client, h, trabajador_id, "2026-08-20").json()

    items = client.get("/api/v1/rrhh/solicitudes-permiso", headers=h).json()["items"]
    assert [i["id"] for i in items] == [temprano["id"], tarde["id"]]


# --- Asistencia ---------------------------------------------------------------
def test_asistencia_por_rango(env):  # noqa: F811
    client, ids, _ = env
    h = _token(client)
    trabajador_id = _trabajador(client, h, ids)
    fecha = "2026-08-04"
    r = client.post(
        "/api/v1/rrhh/asistencia/entrada",
        headers=h,
        json={
            "trabajador_id": trabajador_id,
            "fecha": fecha,
            "hora_entrada": "08:00:00",
        },
    )
    assert r.status_code == 201, r.text

    dentro = client.get(
        f"/api/v1/rrhh/asistencia?desde={fecha}&hasta={fecha}", headers=h
    ).json()
    assert dentro["total"] == 1
    fuera = client.get(
        "/api/v1/rrhh/asistencia?desde=2020-01-01&hasta=2020-01-31", headers=h
    ).json()
    assert fuera["total"] == 0


def test_asistencia_con_rango_invertido_400(env):  # noqa: F811
    client, _, _ = env
    r = client.get(
        "/api/v1/rrhh/asistencia?desde=2026-08-05&hasta=2026-08-01",
        headers=_token(client),
    )
    assert r.status_code == 400
