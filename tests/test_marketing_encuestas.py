"""La encuesta de satisfacción como **conversación**, no como formulario.

Lo que se prueba acá no es que se guarde una fila: es que el guion ramifique
—un 2 de 5 pregunta qué falló y un 5 no—, que el primer "ok" del cliente no
se cuente como puntaje, que nadie conteste una encuesta ajena firmando mal
el webhook, y que una encuesta sin responder termine expirando sola.

Reusa el entorno de `test_marketing.py`: misma organización semilla, mismo
cliente con teléfono, misma venta entregada.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.config.settings import settings
from src.core.celery_app import celery_app
from src.modules.marketing.application import conversacion, encuestas, envios, tasks
from src.modules.marketing.domain import encuesta_flujo
from src.modules.marketing.infrastructure.models import (
    EncuestaPlantilla,
    EncuestaRespuesta,
    EncuestaSatisfaccion,
)
from src.shared.integrations import whatsapp
from tests.test_marketing import _token, _venta, env  # noqa: F401 — fixture reusada

FIRMA_SECRETO = "secreto-de-prueba"


class ClienteWhatsAppFalso:
    """Doble del adaptador: registra qué se mandó, no habla con nadie."""

    enviados: list[tuple] = []

    def enviar_plantilla(self, telefono, nombre, idioma, parametros):
        self.enviados.append(("plantilla", telefono, nombre, tuple(parametros)))
        return "wamid.PLANTILLA"

    def enviar_texto(self, telefono, texto):
        self.enviados.append(("texto", telefono, texto, ()))
        return "wamid.TEXTO"

    def enviar_opciones(self, telefono, texto, opciones):
        self.enviados.append(("opciones", telefono, texto, tuple(opciones)))
        return "wamid.OPCIONES"


@pytest.fixture()
def wa(env, monkeypatch):  # noqa: F811
    """Entorno con WhatsApp 'configurado' y la cola corriendo en línea."""
    client, ids, TestSession = env
    ClienteWhatsAppFalso.enviados = []
    monkeypatch.setattr(settings, "whatsapp_token", "token-de-prueba")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "1234567890")
    monkeypatch.setattr(settings, "whatsapp_app_secret", FIRMA_SECRETO)
    monkeypatch.setattr(settings, "whatsapp_verify_token", "verifica-me")
    monkeypatch.setattr(settings, "marketing_url_publica", "https://encuestas.majambo.pe")
    monkeypatch.setattr(envios, "cliente_factory", ClienteWhatsAppFalso)
    monkeypatch.setattr(tasks, "session_factory", TestSession)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    return client, ids, TestSession


def _firmar(cuerpo: bytes) -> str:
    import hashlib
    import hmac

    return "sha256=" + hmac.new(FIRMA_SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()


def _webhook_texto(telefono: str, texto: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": f"wamid.{texto}",
                                    "from": telefono,
                                    "type": "text",
                                    "text": {"body": texto},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def _enviar_encuesta(client, headers, TestSession, ids, numero=90, canal="whatsapp"):
    venta_id = _venta(TestSession, ids, entregada=True, numero=numero)
    r = client.post(
        "/api/v1/marketing/encuestas",
        headers=headers,
        json={"venta_id": venta_id, "canal": canal},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Dominio: el guion ------------------------------------------------------


def _nodo_puntaje() -> encuesta_flujo.Nodo:
    return encuesta_flujo.Nodo(
        codigo="puntaje",
        tipo="escala",
        siguiente_codigo="recomendaria",
        saltos={"1": "que_fallo", "2": "que_fallo"},
    )


def test_la_respuesta_elige_la_rama():
    nodo = _nodo_puntaje()
    assert encuesta_flujo.siguiente_codigo(nodo, "2") == "que_fallo"
    assert encuesta_flujo.siguiente_codigo(nodo, "5") == "recomendaria"


def test_se_normaliza_lo_que_el_cliente_escribe_de_verdad():
    """Contestar por WhatsApp es escribir, no elegir: sin normalizar, media
    encuesta se rechaza por un acento o un espacio."""
    si_no = encuesta_flujo.Nodo(codigo="rec", tipo="si_no")
    assert encuesta_flujo.normalizar(si_no, " Sí ") == "si"
    assert encuesta_flujo.normalizar(si_no, "NO") == "no"
    escala = _nodo_puntaje()
    assert encuesta_flujo.normalizar(escala, "5 estrellas") == "5"
    assert not encuesta_flujo.valor_valido(escala, encuesta_flujo.normalizar(escala, "9"))


def test_un_guion_ciclico_no_pasa_la_validacion():
    """A → B → A le escribiría al cliente para siempre."""
    nodos = [
        encuesta_flujo.Nodo(codigo="a", tipo="texto", siguiente_codigo="b"),
        encuesta_flujo.Nodo(codigo="b", tipo="texto", siguiente_codigo="a"),
    ]
    problemas = encuesta_flujo.plantilla_coherente(nodos)
    assert any("ciclo" in p for p in problemas)


def test_un_salto_a_un_nodo_inexistente_no_pasa():
    nodos = [encuesta_flujo.Nodo(codigo="a", tipo="texto", siguiente_codigo="fantasma")]
    assert encuesta_flujo.plantilla_coherente(nodos)


# --- Plantilla --------------------------------------------------------------


def test_activar_una_plantilla_desactiva_la_anterior(env):  # noqa: F811
    """Dos guiones vivos parten la serie histórica en dos mitades que no se
    pueden comparar, y nadie se entera hasta que el reporte no cuadra."""
    client, ids, TestSession = env
    h = _token(client)
    nueva = client.post(
        "/api/v1/marketing/encuestas/plantillas",
        headers=h,
        json={
            "nombre": "NPS corto",
            "saludo": "¿Nos ayudas?",
            "activa": True,
            "preguntas": [
                {"codigo": "puntaje", "texto": "Del 1 al 5", "tipo": "escala",
                 "es_puntaje": True}
            ],
        },
    )
    assert nueva.status_code == 201, nueva.text
    with TestSession() as s:
        activas = list(
            s.scalars(select(EncuestaPlantilla).where(EncuestaPlantilla.activa.is_(True)))
        )
    assert [p.nombre for p in activas] == ["NPS corto"]


def test_una_plantilla_con_guion_roto_se_rechaza(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    r = client.post(
        "/api/v1/marketing/encuestas/plantillas",
        headers=h,
        json={
            "nombre": "Rota",
            "saludo": "Hola",
            "preguntas": [
                {
                    "codigo": "a",
                    "texto": "Pregunta",
                    "tipo": "texto",
                    "siguiente_codigo": "no_existe",
                }
            ],
        },
    )
    assert r.status_code == 409
    assert "no existe" in r.json()["detail"]


# --- Envío real por WhatsApp ------------------------------------------------


def test_el_primer_mensaje_es_la_plantilla_aprobada(wa):
    """Fuera de la ventana de 24 h Meta no acepta otra cosa: si esto sale
    como texto suelto, la encuesta nunca llega."""
    client, ids, TestSession = wa
    h = _token(client)
    cuerpo = _enviar_encuesta(client, h, TestSession, ids)

    tipos = [e[0] for e in ClienteWhatsAppFalso.enviados]
    assert tipos == ["plantilla"]
    _, telefono, _, parametros = ClienteWhatsAppFalso.enviados[0]
    assert telefono == "51999888777"  # normalizado a E.164 desde "999888777"
    assert cuerpo["url_publica"] in parametros


def test_el_primer_ok_del_cliente_no_es_el_puntaje(wa):
    """Ese "sí" solo abre la ventana de 24 h. Contarlo como respuesta dejaría
    a media base con el puntaje de haber dicho que sí."""
    client, ids, TestSession = wa
    h = _token(client)
    _enviar_encuesta(client, h, TestSession, ids)
    ClienteWhatsAppFalso.enviados = []

    payload = _webhook_texto("999888777", "ok")
    import json

    crudo = json.dumps(payload).encode()
    r = client.post(
        "/api/v1/webhooks/whatsapp",
        content=crudo,
        headers={"X-Hub-Signature-256": _firmar(crudo), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["procesados"] == 1

    with TestSession() as s:
        encuesta = s.scalar(select(EncuestaSatisfaccion))
        assert encuesta.conversacion_abierta is True
        assert encuesta.puntaje is None
        assert s.scalars(select(EncuestaRespuesta)).first() is None
    # Y recién ahora sale la primera pregunta, con sus opciones.
    assert [e[0] for e in ClienteWhatsAppFalso.enviados] == ["opciones"]


def test_el_webhook_sin_firma_valida_no_toca_nada(wa):
    client, ids, TestSession = wa
    h = _token(client)
    _enviar_encuesta(client, h, TestSession, ids)

    import json

    crudo = json.dumps(_webhook_texto("999888777", "5")).encode()
    r = client.post(
        "/api/v1/webhooks/whatsapp",
        content=crudo,
        headers={"X-Hub-Signature-256": "sha256=falsa", "Content-Type": "application/json"},
    )
    assert r.status_code == 403
    with TestSession() as s:
        assert s.scalar(select(EncuestaSatisfaccion)).conversacion_abierta is False


def test_la_conversacion_avanza_nodo_a_nodo_por_whatsapp(wa):
    client, ids, TestSession = wa
    h = _token(client)
    cuerpo = _enviar_encuesta(client, h, TestSession, ids)
    encuesta_id = uuid.UUID(cuerpo["encuesta"]["id"])

    with TestSession() as s:
        encuesta = s.get(EncuestaSatisfaccion, encuesta_id)
        envios.abrir_conversacion(s, encuesta)
        s.commit()

    def entra(texto):
        with TestSession() as s:
            mensaje = whatsapp.MensajeEntrante(
                mensaje_id=f"wamid.{texto}",
                telefono="51999888777",
                texto=texto,
                opcion_id=None,
            )
            assert conversacion.procesar_mensaje(s, mensaje) is True

    entra("2")  # puntaje bajo ⇒ rama "¿qué falló?"
    with TestSession() as s:
        encuesta = s.get(EncuestaSatisfaccion, encuesta_id)
        assert encuesta.puntaje == 2
        assert encuestas.pregunta_actual(s, encuesta).codigo == "que_fallo"

    entra("tiempo")
    entra("Llegó frío")
    with TestSession() as s:
        encuesta = s.get(EncuestaSatisfaccion, encuesta_id)
        assert encuesta.estado == "respondida"
        assert encuesta.comentario == "Llegó frío"
        valores = {
            r.valor for r in s.scalars(select(EncuestaRespuesta)) if r.encuesta_id == encuesta_id
        }
        assert valores == {"2", "tiempo", "Llegó frío"}


def test_una_respuesta_invalida_repite_la_pregunta(wa):
    """El cliente no sabe que hay un guion: cortarle la conversación por
    escribir '9' pierde la encuesta entera."""
    client, ids, TestSession = wa
    h = _token(client)
    cuerpo = _enviar_encuesta(client, h, TestSession, ids)
    encuesta_id = uuid.UUID(cuerpo["encuesta"]["id"])
    with TestSession() as s:
        envios.abrir_conversacion(s, s.get(EncuestaSatisfaccion, encuesta_id))
        s.commit()
    ClienteWhatsAppFalso.enviados = []

    with TestSession() as s:
        conversacion.procesar_mensaje(
            s,
            whatsapp.MensajeEntrante("wamid.x", "51999888777", "nueve", None),
        )
    with TestSession() as s:
        encuesta = s.get(EncuestaSatisfaccion, encuesta_id)
        assert encuesta.puntaje is None
        assert encuestas.pregunta_actual(s, encuesta).codigo == "puntaje"
    assert [e[0] for e in ClienteWhatsAppFalso.enviados] == ["opciones"]


def test_un_numero_sin_encuesta_abierta_se_ignora(wa):
    client, ids, TestSession = wa
    with TestSession() as s:
        movido = conversacion.procesar_mensaje(
            s, whatsapp.MensajeEntrante("wamid.z", "51900000000", "hola", None)
        )
    assert movido is False


def test_sin_telefono_no_se_manda_por_whatsapp(wa):
    """Prefiere fallar al crear la encuesta antes que dejar una `enviada` que
    nunca salió: el porcentaje de respuesta contaría un envío inexistente."""
    client, ids, TestSession = wa
    h = _token(client)
    from src.modules.sales.infrastructure.models import Cliente

    with TestSession() as s:
        cliente = s.get(Cliente, uuid.UUID(ids["cliente_id"]))
        cliente.contacto = None
        s.commit()

    venta_id = _venta(TestSession, ids, entregada=True, numero=93)
    r = client.post(
        "/api/v1/marketing/encuestas",
        headers=h,
        json={"venta_id": venta_id, "canal": "whatsapp"},
    )
    assert r.status_code == 409
    assert "teléfono" in r.json()["detail"]


# --- Enlace público ---------------------------------------------------------


def test_el_enlace_publico_contesta_sin_cuenta_y_no_filtra_el_pedido(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    cuerpo = _enviar_encuesta(client, h, TestSession, ids, numero=95, canal="link")
    with TestSession() as s:
        token = s.get(
            EncuestaSatisfaccion, uuid.UUID(cuerpo["encuesta"]["id"])
        ).token_publico

    vista = client.get(f"/api/v1/marketing/publico/encuestas/{token}")
    assert vista.status_code == 200
    assert vista.json()["pregunta"]["codigo"] == "puntaje"
    # El token es una credencial anónima: nada del pedido puede salir por acá.
    assert "venta_id" not in vista.text and "cliente_id" not in vista.text

    paso = client.post(
        f"/api/v1/marketing/publico/encuestas/{token}/respuesta", json={"valor": "1"}
    )
    assert paso.json()["pregunta"]["codigo"] == "que_fallo"


def test_una_encuesta_expirada_no_admite_respuesta_publica(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    cuerpo = _enviar_encuesta(client, h, TestSession, ids, numero=96, canal="link")
    encuesta_id = uuid.UUID(cuerpo["encuesta"]["id"])
    with TestSession() as s:
        encuesta = s.get(EncuestaSatisfaccion, encuesta_id)
        encuesta.fecha_expiracion = datetime.now(UTC) - timedelta(hours=1)
        s.commit()
        assert encuestas.expirar_vencidas(s) == 1
        s.commit()

    with TestSession() as s:
        token = s.get(EncuestaSatisfaccion, encuesta_id).token_publico
    r = client.post(
        f"/api/v1/marketing/publico/encuestas/{token}/respuesta", json={"valor": "5"}
    )
    assert r.status_code == 409


def test_el_barrido_solo_expira_lo_vencido(env):  # noqa: F811
    client, ids, TestSession = env
    h = _token(client)
    _enviar_encuesta(client, h, TestSession, ids, numero=97, canal="link")
    with TestSession() as s:
        assert encuestas.expirar_vencidas(s) == 0


# --- Handshake del webhook --------------------------------------------------


def test_el_handshake_devuelve_el_desafio_solo_con_el_token_correcto(wa):
    client, ids, TestSession = wa
    ok = client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verifica-me",
            "hub.challenge": "1234",
        },
    )
    assert ok.status_code == 200 and ok.text == "1234"

    mal = client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "otro",
            "hub.challenge": "1234",
        },
    )
    assert mal.status_code == 403
