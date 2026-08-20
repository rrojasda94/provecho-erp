"""Tests del requerimiento de la jornada (ADR-051, RN-INV-023/024).

La lista que el turno junta durante el día: se arma sola con lo que está bajo
mínimo, admite lo que el personal decide pedir aparte, y el almacén recibe la
diferencia entre una cosa y la otra.

Reusa la fixture de `test_transferencias` (mismo escenario: central, dos
locales de la misma sucursal, un perecible y un suministro).
"""

import uuid
from decimal import Decimal

from sqlalchemy import select

from src.modules.inventory.infrastructure.models import SolicitudInsumos, Stock
from src.modules.users.infrastructure.models import Almacen, Marca, Sucursal
from tests.test_transferencias import (  # noqa: F401 — fixture reusada
    _ingresar,
    _token,
    env,
)

BASE = "/api/v1/inventory"


def _minimo(TestSession, almacen_id, sku_id, minimo):
    """No hay API para el punto de reorden en este slice: se fija directo."""
    with TestSession() as s:
        fila = s.scalar(
            select(Stock).where(
                Stock.almacen_id == uuid.UUID(almacen_id),
                Stock.sku_id == uuid.UUID(sku_id),
            )
        )
        fila.stock_minimo = Decimal(minimo)
        s.commit()


def _borrador(client, h, almacen_id):
    r = client.get(f"{BASE}/solicitudes/borrador?almacen_id={almacen_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _item(detalle, sku_id):
    return next((i for i in detalle["items"] if i["sku_id"] == sku_id), None)


def test_el_borrador_se_arma_solo_con_lo_que_esta_bajo_minimo(env):  # noqa: F811
    """El botón no abre una lista vacía: abre lo que hay que reponer."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)

    detalle = _borrador(client, h, ids["local_id"])

    assert detalle["estado"] == "borrador"
    item = _item(detalle, ids["sku_servilleta"])
    assert item is not None
    assert item["bajo_minimo_al_pedir"] is True
    # Faltan 8 para volver al mínimo de 10 con 2 en el almacén.
    assert Decimal(item["cantidad_solicitada"]) == Decimal(8)


def test_el_borrador_es_uno_por_almacen_y_no_se_duplica(env):  # noqa: F811
    """Dos personas del mismo turno abren la misma lista (RN-INV-023): dos
    listas paralelas serían dos pedidos que se solapan y ninguno completo."""
    client, ids, TestSession = env
    h_alm = _token(client, "almacenero1", "654321")
    h_admin = _token(client)
    _ingresar(client, h_alm, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)

    primero = _borrador(client, h_alm, ids["local_id"])
    segundo = _borrador(client, h_admin, ids["local_id"])

    assert primero["id"] == segundo["id"]
    assert len(segundo["items"]) == 1
    with TestSession() as s:
        borradores = s.scalars(
            select(SolicitudInsumos).where(SolicitudInsumos.estado == "borrador")
        ).all()
    assert len(borradores) == 1


def test_el_refresco_suma_lo_nuevo_sin_pisar_lo_tecleado(env):  # noqa: F811
    """Lo que el personal escribió es una decisión tomada: la sugerencia se
    suma al lado, nunca encima."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])

    r = client.patch(
        f"{BASE}/solicitudes/{borrador['id']}/items/{ids['sku_servilleta']}",
        headers=h,
        json={"cantidad": "3"},
    )
    assert r.status_code == 200, r.text

    # El queso cae bajo mínimo recién ahora.
    _ingresar(client, h, ids["local_id"], ids["sku_queso"], 1)
    _minimo(TestSession, ids["local_id"], ids["sku_queso"], 4)

    detalle = _borrador(client, h, ids["local_id"])

    assert Decimal(_item(detalle, ids["sku_servilleta"])["cantidad_solicitada"]) == 3
    queso = _item(detalle, ids["sku_queso"])
    assert queso is not None and queso["bajo_minimo_al_pedir"] is True


def test_lo_que_el_local_agrega_a_mano_no_viaja_como_urgencia(env):  # noqa: F811
    """RN-INV-024: sigue siendo un pedido legítimo, pero el almacenero tiene
    que poder ver que no está por faltar."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    # El queso está con stock de sobra: nadie lo necesita, el local lo quiere.
    _ingresar(client, h, ids["local_id"], ids["sku_queso"], 50)
    _minimo(TestSession, ids["local_id"], ids["sku_queso"], 4)
    borrador = _borrador(client, h, ids["local_id"])

    r = client.post(
        f"{BASE}/solicitudes/{borrador['id']}/items",
        headers=h,
        json={"sku_id": ids["sku_queso"], "cantidad": "6"},
    )
    assert r.status_code == 201, r.text

    detalle = r.json()
    assert _item(detalle, ids["sku_queso"])["bajo_minimo_al_pedir"] is False
    assert _item(detalle, ids["sku_servilleta"])["bajo_minimo_al_pedir"] is True

    # Y el mismo SKU no entra dos veces: se cambia su cantidad.
    repetido = client.post(
        f"{BASE}/solicitudes/{borrador['id']}/items",
        headers=h,
        json={"sku_id": ids["sku_queso"], "cantidad": "2"},
    )
    assert repetido.status_code == 409, repetido.text


def test_el_borrador_no_aparece_como_solicitud_hasta_que_se_envia(env):  # noqa: F811
    """Una lista que nadie envió todavía no le pidió nada a nadie."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])

    listado = client.get(f"{BASE}/solicitudes", headers=h).json()["items"]
    assert borrador["id"] not in [s["id"] for s in listado]

    r = client.post(f"{BASE}/solicitudes/{borrador['id']}/enviar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pendiente"

    listado = client.get(f"{BASE}/solicitudes", headers=h).json()["items"]
    assert borrador["id"] in [s["id"] for s in listado]
    # Y pedirlo explícitamente sigue funcionando: la pantalla del borrador lo
    # necesita para saber si hay uno abierto.
    solo_borradores = client.get(
        f"{BASE}/solicitudes?estado=borrador", headers=h
    ).json()["items"]
    assert solo_borradores == []


def test_un_borrador_sin_items_no_se_envia(env):  # noqa: F811
    """Enviar una lista vacía habría creado una solicitud que no pide nada y
    que igual ocupa a un aprobador."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])

    r = client.delete(
        f"{BASE}/solicitudes/{borrador['id']}/items/{ids['sku_servilleta']}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []

    r = client.post(f"{BASE}/solicitudes/{borrador['id']}/enviar", headers=h)
    assert r.status_code == 409, r.text


def test_una_solicitud_enviada_ya_no_se_edita(env):  # noqa: F811
    """Editar después de enviar cambiaría lo que el aprobador está mirando."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])
    client.post(f"{BASE}/solicitudes/{borrador['id']}/enviar", headers=h)

    r = client.post(
        f"{BASE}/solicitudes/{borrador['id']}/items",
        headers=h,
        json={"sku_id": ids["sku_queso"], "cantidad": "1"},
    )
    assert r.status_code == 409, r.text
    assert "ya no se edita" in r.json()["detail"]


def test_descartar_el_borrador_lo_cancela(env):  # noqa: F811
    """Se descarta por el mismo camino que se cancela una solicitud: nunca
    reservó nada, así que liberar no tiene qué soltar."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])

    r = client.post(f"{BASE}/solicitudes/{borrador['id']}/cancelar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelada"

    # Y el siguiente botón abre uno nuevo, no revive el descartado.
    nuevo = _borrador(client, h, ids["local_id"])
    assert nuevo["id"] != borrador["id"]


def test_el_listado_filtra_por_sucursal_y_por_marca(env):  # noqa: F811
    """El requerimiento vive por almacén; sucursal y marca cuelgan de él."""
    client, ids, TestSession = env
    h = _token(client, "almacenero1", "654321")
    _ingresar(client, h, ids["local_id"], ids["sku_servilleta"], 2)
    _minimo(TestSession, ids["local_id"], ids["sku_servilleta"], 10)
    borrador = _borrador(client, h, ids["local_id"])
    client.post(f"{BASE}/solicitudes/{borrador['id']}/enviar", headers=h)

    with TestSession() as s:
        almacen = s.get(Almacen, uuid.UUID(ids["local_id"]))
        sucursal = s.get(Sucursal, almacen.sucursal_id)
        marca_id = str(sucursal.marca_id)
        sucursal_id = str(sucursal.id)
        marca = s.get(Marca, sucursal.marca_id)
        otra_marca = Marca(
            grupo_id=marca.grupo_id, nombre="Otra Marca", tipo="restaurante"
        )
        s.add(otra_marca)
        s.commit()
        otra_marca_id = str(otra_marca.id)

    def ids_de(query):
        respuesta = client.get(f"{BASE}/solicitudes?{query}", headers=h)
        return [x["id"] for x in respuesta.json()["items"]]

    assert borrador["id"] in ids_de(f"sucursal_id={sucursal_id}")
    assert borrador["id"] in ids_de(f"marca_id={marca_id}")
    assert ids_de(f"marca_id={otra_marca_id}") == []
    assert ids_de(f"sucursal_id={uuid.uuid4()}") == []
