"""Calendario de contenido **con el arte**, no solo con el título.

`pieza_contenido` guardaba título, canal, fecha y métricas: todo menos la
pieza. Un calendario sin el arte obliga a abrir otra carpeta para saber qué
se publica el jueves, y ahí es donde se publica la versión vieja del banner.
"""

from tests.test_marketing import (  # noqa: F401 — fixture reusada
    _crear_campana,
    _token,
    env,
)

ARTE = {
    "nombre": "banner-verano.png",
    "mime_type": "image/png",
    "tamano_bytes": 245_000,
    "url_storage": "s3://provecho/marketing/banner-verano.png",
}


def _pieza(client, h, ids, *, fecha="2026-08-12", titulo="Reel de verano", campana_id=None):
    body = {
        "marca_id": ids["marca_id"],
        "titulo": titulo,
        "canal": "instagram",
        "fecha_publicacion": fecha,
        "pertinente_marca": True,
        "uso_marca_validado": True,
    }
    if campana_id:
        body["campana_id"] = campana_id
    r = client.post("/api/v1/marketing/piezas", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_el_calendario_agrupa_por_dia_y_cuenta_los_adjuntos(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    primera = _pieza(client, h, ids, fecha="2026-08-12", titulo="Reel de verano")
    _pieza(client, h, ids, fecha="2026-08-12", titulo="Historia de verano")
    _pieza(client, h, ids, fecha="2026-08-20", titulo="Post de cierre")

    assert (
        client.post(
            f"/api/v1/marketing/piezas/{primera}/adjuntos", headers=h, json=ARTE
        ).status_code
        == 201
    )

    r = client.get(
        "/api/v1/marketing/piezas/calendario",
        headers=h,
        params={"desde": "2026-08-01", "hasta": "2026-08-15"},
    )
    assert r.status_code == 200
    dias = r.json()["dias"]
    # El 20 queda fuera del rango; el calendario respeta la ventana pedida.
    assert [d["fecha"] for d in dias] == ["2026-08-12"]
    piezas = {p["titulo"]: p["adjuntos"] for p in dias[0]["piezas"]}
    assert piezas == {"Reel de verano": 1, "Historia de verano": 0}


def test_el_adjunto_se_lista_y_se_quita_sin_borrarse(env):  # noqa: F811
    """El arte de una pieza publicada es evidencia de qué se publicó: se saca
    de la vista, no de la historia."""
    client, ids, TestSession = env
    h = _token(client)
    pieza_id = _pieza(client, h, ids)
    archivo_id = client.post(
        f"/api/v1/marketing/piezas/{pieza_id}/adjuntos", headers=h, json=ARTE
    ).json()["id"]

    listados = client.get(f"/api/v1/marketing/piezas/{pieza_id}/adjuntos", headers=h)
    assert [a["nombre"] for a in listados.json()] == ["banner-verano.png"]
    assert listados.json()[0]["extension"] == "png"

    quitado = client.delete(
        f"/api/v1/marketing/piezas/{pieza_id}/adjuntos/{archivo_id}", headers=h
    )
    assert quitado.status_code == 204
    assert client.get(
        f"/api/v1/marketing/piezas/{pieza_id}/adjuntos", headers=h
    ).json() == []

    from src.shared.models import Archivo

    with TestSession() as s:
        import uuid

        assert s.get(Archivo, uuid.UUID(archivo_id)).deleted_at is not None


def test_no_se_adjunta_cualquier_cosa(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    pieza_id = _pieza(client, h, ids)
    r = client.post(
        f"/api/v1/marketing/piezas/{pieza_id}/adjuntos",
        headers=h,
        json=ARTE | {"nombre": "macro.exe", "mime_type": "application/x-msdownload"},
    )
    assert r.status_code == 409


def test_una_pieza_descartada_no_admite_adjuntos(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    pieza_id = _pieza(client, h, ids)
    client.post(f"/api/v1/marketing/piezas/{pieza_id}/descarte", headers=h)
    r = client.post(
        f"/api/v1/marketing/piezas/{pieza_id}/adjuntos", headers=h, json=ARTE
    )
    assert r.status_code == 409


def test_el_listado_plano_filtra_por_rango(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    _pieza(client, h, ids, fecha="2026-08-12", titulo="Dentro del rango")
    _pieza(client, h, ids, fecha="2026-09-30", titulo="Fuera del rango")

    r = client.get(
        "/api/v1/marketing/piezas",
        headers=h,
        params={"desde": "2026-08-01", "hasta": "2026-08-31"},
    )
    assert [p["titulo"] for p in r.json()["items"]] == ["Dentro del rango"]
