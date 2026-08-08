"""Evaluación agencia vs. interna (RN-MKT-006) y el acumulado de campaña.

Lo que se prueba de la evaluación no es que guarde propuestas: es que la
comparación **se pueda auditar**. Criterios ponderados congelados antes de
ver las ofertas, la opción interna obligada a competir, y quien se aparta de
la recomendación o del presupuesto obligado a dejarlo escrito.

Del acumulado se prueba que exista un consumidor: hasta este cambio,
`campana_lanzada` y `lead_generado` se publicaban al vacío.
"""

import uuid

import pytest
from sqlalchemy import select

from src.modules.marketing.domain import agencia
from src.modules.marketing.infrastructure.models import CampanaMetrica
from tests.test_marketing import (  # noqa: F401 — fixture reusada
    _crear_campana,
    _lanzar,
    _token,
    _venta,
    env,
)

CRITERIOS = [
    {"codigo": "experiencia", "etiqueta": "Experiencia en rubro", "peso": 40},
    {"codigo": "precio", "etiqueta": "Precio", "peso": 40},
    {"codigo": "plazo", "etiqueta": "Plazo", "peso": 20},
]


@pytest.fixture()
def campana(env):  # noqa: F811
    """Campaña ya lanzada: sin brief aprobado no hay contra qué evaluar."""
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="agencia-key-1").json()["id"]
    _lanzar(client, h, campana_id)
    return client, h, ids, TestSession, campana_id


def _evaluacion(client, h, campana_id, presupuesto="5000.00"):
    r = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/evaluaciones-agencia",
        headers=h,
        json={
            "objetivo": "Campaña de verano en redes",
            "presupuesto_referencia": presupuesto,
            "criterios": CRITERIOS,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _opcion(client, h, evaluacion_id, **kwargs):
    body = {
        "tipo": "agencia",
        "nombre": "Agencia A",
        "costo": "4000.00",
        "plazo_dias": 30,
        "puntajes": {"experiencia": 5, "precio": 3, "plazo": 4},
    } | kwargs
    return client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/opciones",
        headers=h,
        json=body,
    )


# --- Dominio ----------------------------------------------------------------


def test_el_ponderado_usa_los_pesos_declarados():
    puntaje = agencia.puntaje_ponderado(CRITERIOS, {"experiencia": 5, "precio": 3, "plazo": 4})
    # (5*40 + 3*40 + 4*20) / 100
    assert str(puntaje) == "4.00"


def test_un_criterio_sin_puntuar_vale_cero_y_no_achica_el_divisor():
    """Dejar en blanco lo que no conviene sería la forma más fácil de ganar
    la comparación."""
    completo = agencia.puntaje_ponderado(CRITERIOS, {"experiencia": 5, "precio": 5, "plazo": 5})
    parcial = agencia.puntaje_ponderado(CRITERIOS, {"experiencia": 5})
    assert completo > parcial


def test_la_recomendada_sale_de_las_que_caben_en_el_presupuesto():
    cara = agencia.Propuesta("cara", "agencia", costo=9000, puntaje_total=5)
    justa = agencia.Propuesta("justa", "interna", costo=3000, puntaje_total=3)
    assert agencia.recomendada([cara, justa], presupuesto=5000).id == "justa"
    # Si ninguna cabe, igual devuelve la mejor: la decisión sube a Gerencia,
    # y para decidir necesita ver un candidato.
    assert agencia.recomendada([cara], presupuesto=5000).id == "cara"


# --- API --------------------------------------------------------------------


def test_los_pesos_tienen_que_sumar_cien(campana):
    client, h, ids, TestSession, campana_id = campana
    r = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/evaluaciones-agencia",
        headers=h,
        json={
            "objetivo": "Verano",
            "presupuesto_referencia": "5000.00",
            "criterios": [{"codigo": "precio", "etiqueta": "Precio", "peso": 60}],
        },
    )
    assert r.status_code == 409
    assert "suman" in r.json()["detail"]


def test_no_se_cierra_la_evaluacion_sin_la_opcion_interna(campana):
    """Elegir entre tres agencias no contesta si hace falta una agencia."""
    client, h, ids, TestSession, campana_id = campana
    evaluacion_id = _evaluacion(client, h, campana_id)
    _opcion(client, h, evaluacion_id, nombre="Agencia A")
    _opcion(client, h, evaluacion_id, nombre="Agencia B", costo="3500.00")

    r = client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/cierre", headers=h
    )
    assert r.status_code == 409
    assert "interna" in r.json()["detail"]


def test_apartarse_de_la_recomendada_exige_motivo(campana):
    client, h, ids, TestSession, campana_id = campana
    evaluacion_id = _evaluacion(client, h, campana_id)
    mejor = _opcion(
        client, h, evaluacion_id, nombre="Agencia A", costo="4000.00",
        puntajes={"experiencia": 5, "precio": 5, "plazo": 5},
    ).json()
    peor = _opcion(
        client, h, evaluacion_id, tipo="interna", nombre="Equipo interno",
        costo="1000.00", puntajes={"experiencia": 2, "precio": 5, "plazo": 2},
    ).json()

    cierre = client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/cierre", headers=h
    )
    assert cierre.status_code == 200
    assert cierre.json()["opcion_recomendada_id"] == mejor["id"]

    sin_motivo = client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/decision",
        headers=h,
        json={"opcion_id": peor["id"]},
    )
    assert sin_motivo.status_code == 409

    con_motivo = client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/decision",
        headers=h,
        json={"opcion_id": peor["id"], "motivo": "Preferimos capacidad propia este año"},
    )
    assert con_motivo.status_code == 200
    assert con_motivo.json()["estado"] == "decidida"
    assert con_motivo.json()["opcion_elegida_id"] == peor["id"]


def test_quien_evalua_no_decide(campana):
    """El rol `marketing` arma la comparación; firmarla es de Gerencia
    (RN-MKT-006), igual que el brief (RN-MKT-003)."""
    client, h, ids, TestSession, campana_id = campana
    h_mkt = _token(client, username="mkt1", pin="111111")
    evaluacion_id = _evaluacion(client, h_mkt, campana_id)
    # El rol `marketing` sí carga propuestas…
    elegida = _opcion(client, h_mkt, evaluacion_id).json()
    _opcion(client, h_mkt, evaluacion_id, tipo="interna", nombre="Equipo interno",
            costo="1000.00", puntajes={"experiencia": 2, "precio": 5, "plazo": 2})
    assert client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/cierre", headers=h_mkt
    ).status_code == 200

    # …y no firma la decisión.
    r = client.post(
        f"/api/v1/marketing/evaluaciones-agencia/{evaluacion_id}/decision",
        headers=h_mkt,
        json={"opcion_id": elegida["id"]},
    )
    assert r.status_code == 403


def test_no_se_evalua_una_campana_en_brief(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="agencia-key-2").json()["id"]
    r = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/evaluaciones-agencia",
        headers=h,
        json={
            "objetivo": "Verano",
            "presupuesto_referencia": "5000.00",
            "criterios": CRITERIOS,
        },
    )
    assert r.status_code == 409


# --- Acumulado de campaña (consumidor de los eventos propios) ---------------


def test_lanzar_una_campana_y_generar_leads_mueve_el_acumulado(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="metrica-key-1").json()["id"]
    _lanzar(client, h, campana_id)

    client.post(
        "/api/v1/marketing/leads",
        headers=h,
        json={
            "campana_id": campana_id,
            "canal": "instagram",
            "tipo": "contacto",
            "cliente_id": ids["cliente_id"],
            "idempotency_key": "lead-metrica-1",
        },
    )

    r = client.get(f"/api/v1/marketing/campanas/{campana_id}/metricas", headers=h)
    assert r.status_code == 200
    datos = r.json()
    assert datos["fecha_lanzamiento"] is not None
    assert datos["leads_generados"] == 1
    assert datos["leads_convertidos"] == 0
    assert datos["tasa_conversion"] == 0.0


def test_la_atribucion_manual_cuenta_la_conversion(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="metrica-key-2").json()["id"]
    _lanzar(client, h, campana_id)
    lead_id = client.post(
        "/api/v1/marketing/leads",
        headers=h,
        json={
            "campana_id": campana_id,
            "canal": "instagram",
            "tipo": "contacto",
            "cliente_id": ids["cliente_id"],
            "idempotency_key": "lead-metrica-2",
        },
    ).json()["id"]
    venta_id = _venta(TestSession, ids, entregada=True, numero=80)

    client.post(
        f"/api/v1/marketing/leads/{lead_id}/atribucion",
        headers=h,
        json={"venta_id": venta_id},
    )
    datos = client.get(
        f"/api/v1/marketing/campanas/{campana_id}/metricas", headers=h
    ).json()
    assert datos["leads_convertidos"] == 1
    assert datos["tasa_conversion"] == 1.0

    # La encuesta de esa venta se le acredita a la campaña por el lead.
    client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "link"},
    )
    datos = client.get(
        f"/api/v1/marketing/campanas/{campana_id}/metricas", headers=h
    ).json()
    assert datos["encuestas_enviadas"] == 1


def test_el_recalculo_repara_un_acumulado_corrompido(env):  # noqa: F811
    """El acumulado se mantiene por eventos: un worker caído lo deja corto y
    sin recálculo no habría forma de corregirlo."""
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="metrica-key-3").json()["id"]
    _lanzar(client, h, campana_id)
    client.post(
        "/api/v1/marketing/leads",
        headers=h,
        json={
            "campana_id": campana_id,
            "canal": "instagram",
            "tipo": "contacto",
            "idempotency_key": "lead-metrica-3",
        },
    )
    with TestSession() as s:
        fila = s.scalar(
            select(CampanaMetrica).where(CampanaMetrica.campana_id == uuid.UUID(campana_id))
        )
        fila.leads_generados = 0
        s.commit()

    reparado = client.post(
        f"/api/v1/marketing/campanas/{campana_id}/metricas/recalculo", headers=h
    )
    assert reparado.json()["leads_generados"] == 1


def test_una_pieza_publicada_suma_a_su_campana(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    campana_id = _crear_campana(client, h, ids, key="metrica-key-4").json()["id"]
    _lanzar(client, h, campana_id)
    pieza_id = client.post(
        "/api/v1/marketing/piezas",
        headers=h,
        json={
            "marca_id": ids["marca_id"],
            "titulo": "Reel de verano",
            "canal": "instagram",
            "fecha_publicacion": "2026-08-10",
            "campana_id": campana_id,
            "pertinente_marca": True,
            "uso_marca_validado": True,
        },
    ).json()["id"]
    client.post(f"/api/v1/marketing/piezas/{pieza_id}/publicacion", headers=h, json={})

    datos = client.get(
        f"/api/v1/marketing/campanas/{campana_id}/metricas", headers=h
    ).json()
    assert datos["piezas_publicadas"] == 1
