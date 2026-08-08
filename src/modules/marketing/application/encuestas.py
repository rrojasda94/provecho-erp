"""Casos de uso de encuesta de satisfacción: enviarla sobre una venta ya
entregada y conducir la conversación nodo por nodo hasta el final.

Selectiva a propósito (RN-COM-007): Marketing elige a qué venta entregada le
manda encuesta. No hay envío automático masivo. El estado de entrega se lee
por el contrato público de `sales` — marketing no toca `Venta`.

**Por qué nodos y no un formulario.** La encuesta viaja por WhatsApp, donde
no hay formulario: hay una conversación, un mensaje a la vez. Cada respuesta
decide cuál es la siguiente pregunta —un 2 de 5 pregunta qué salió mal, un 5
pregunta si nos recomendaría—, así que la fila tiene que recordar en qué
nodo está el cliente. Sin ese estado, un "no" suelto que llega tres horas
después no se puede interpretar.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.marketing.application import plantillas as plantillas_uc
from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import encuesta_flujo
from src.modules.marketing.infrastructure.models import (
    EncuestaPregunta,
    EncuestaRespuesta,
    EncuestaSatisfaccion,
)
from src.modules.marketing.infrastructure.repositories import (
    EncuestaPlantillaRepo,
    EncuestaRepo,
)
from src.modules.sales.application.queries_publicas import (
    contacto_de_cliente,
    venta_para_encuesta,
)
from src.modules.users.infrastructure.models import Sucursal
from src.shared.integrations import whatsapp

# Canales que necesitan un teléfono al que escribirle. `pos` se contesta en
# la tablet del local y `link` por la URL pública: ninguno manda nada.
CANALES_CON_DESTINO = ("whatsapp",)


def enviar_encuesta(
    session: Session,
    *,
    venta_id: uuid.UUID,
    canal: str,
    enviada_por: uuid.UUID,
    plantilla_id: uuid.UUID | None = None,
) -> EncuestaSatisfaccion:
    repo = EncuestaRepo(session)
    existente = repo.de_venta(venta_id)
    if existente is not None:
        return existente

    venta = venta_para_encuesta(session, venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    if not venta["entregada"]:
        raise Conflicto(
            "el pedido todavía no se entregó; la encuesta se envía después de "
            "la entrega (PROC-OPE-002)"
        )
    if venta["cliente_id"] is None:
        raise ReglaNegocio("la venta no tiene cliente registrado; no hay a quién encuestar")

    plantilla = _resolver_plantilla(session, venta["sucursal_id"], plantilla_id)
    primera = plantillas_uc.primera_pregunta(session, plantilla.id)
    if primera is None:
        raise ReglaNegocio("la plantilla activa no tiene preguntas")

    destino = _resolver_destino(session, venta["cliente_id"], canal)
    ahora = datetime.now(UTC)
    encuesta = repo.add(
        EncuestaSatisfaccion(
            venta_id=venta_id,
            cliente_id=venta["cliente_id"],
            canal=canal,
            estado="enviada",
            enviada_por=enviada_por,
            plantilla_id=plantilla.id,
            pregunta_actual_id=primera.id,
            destino=destino,
            token_publico=secrets.token_urlsafe(32),
            fecha_expiracion=ahora
            + timedelta(hours=settings.marketing_encuesta_vigencia_horas),
        )
    )
    # Con `session=`: el despacho espera al commit (ADR-016). El listener que
    # encola el WhatsApp corre en otro proceso y solo puede leer filas ya
    # confirmadas — publicar antes le daría un id que todavía no existe.
    event_bus.publish(
        "marketing.encuesta_enviada",
        {
            "encuesta_id": str(encuesta.id),
            "venta_id": str(venta_id),
            "cliente_id": str(venta["cliente_id"]),
            "canal": canal,
        },
        session=session,
    )
    return encuesta


def responder_nodo(
    session: Session, encuesta: EncuestaSatisfaccion, valor: str
) -> EncuestaPregunta | None:
    """Contesta el nodo actual y devuelve el siguiente (`None` = terminó).

    Idempotente por nodo: la misma respuesta al mismo nodo actualiza la fila
    en vez de duplicarla. WhatsApp reentrega el webhook ante cualquier error
    y un doble toque en el botón es lo normal, no la excepción.
    """
    if encuesta.estado != "enviada":
        raise Conflicto(f"la encuesta está {encuesta.estado}; no admite respuesta")
    if encuesta.plantilla_id is None:
        return _responder_sin_guion(session, encuesta, valor)

    pregunta = _pregunta_actual(session, encuesta)
    nodo = plantillas_uc.a_nodo(pregunta)
    normalizado = encuesta_flujo.normalizar(nodo, valor)
    if not encuesta_flujo.valor_valido(nodo, normalizado):
        raise ReglaNegocio(_ayuda(pregunta, nodo))

    repo = EncuestaRepo(session)
    fila = repo.respuesta_de(encuesta.id, pregunta.id)
    if fila is None:
        session.add(
            EncuestaRespuesta(
                encuesta_id=encuesta.id, pregunta_id=pregunta.id, valor=normalizado
            )
        )
    else:
        fila.valor = normalizado

    puntaje = encuesta_flujo.puntaje_de(nodo, normalizado)
    if pregunta.es_puntaje and puntaje is not None:
        encuesta.puntaje = puntaje
    if pregunta.tipo == "texto":
        # El último texto libre es "el comentario" del negocio: es el campo
        # que ya leen el reporte y la bandeja, y no vale duplicarlo.
        encuesta.comentario = normalizado[:500]

    siguiente = _siguiente(session, encuesta, nodo, normalizado)
    encuesta.pregunta_actual_id = siguiente.id if siguiente is not None else None
    if siguiente is None:
        _cerrar(session, encuesta)
    session.flush()
    return siguiente


def expirar_encuesta(session: Session, encuesta_id: uuid.UUID) -> EncuestaSatisfaccion:
    encuesta = _encuesta(session, encuesta_id)
    if encuesta.estado != "enviada":
        raise Conflicto(f"la encuesta está {encuesta.estado}; no admite expiración")
    encuesta.estado = "expirada"
    session.flush()
    return encuesta


def expirar_vencidas(session: Session, ahora: datetime | None = None) -> int:
    """Barrido de vigencia. Una respuesta de dos semanas después no mide la
    experiencia de ese pedido: mezclarla con las de esta semana ensucia
    justo el número que la encuesta existe para dar."""
    vencidas = EncuestaRepo(session).vencidas(ahora or datetime.now(UTC))
    for encuesta in vencidas:
        encuesta.estado = "expirada"
        encuesta.pregunta_actual_id = None
    session.flush()
    return len(vencidas)


def url_publica(encuesta: EncuestaSatisfaccion) -> str:
    """Enlace para contestar sin cuenta. Vacío si no hay base configurada —
    el mensaje sale igual, solo que sin enlace."""
    base = settings.marketing_url_publica.rstrip("/")
    return f"{base}/encuestas/{encuesta.token_publico}" if base else ""


def por_token(session: Session, token: str) -> EncuestaSatisfaccion:
    encuesta = EncuestaRepo(session).por_token(token)
    if encuesta is None:
        raise NoEncontrado("encuesta no encontrada")
    return encuesta


def pregunta_actual(
    session: Session, encuesta: EncuestaSatisfaccion
) -> EncuestaPregunta | None:
    if encuesta.pregunta_actual_id is None:
        return None
    return EncuestaPlantillaRepo(session).pregunta(encuesta.pregunta_actual_id)


# --- Interno -----------------------------------------------------------------


def _resolver_plantilla(
    session: Session, sucursal_id: uuid.UUID, plantilla_id: uuid.UUID | None
):
    repo = EncuestaPlantillaRepo(session)
    if plantilla_id is not None:
        plantilla = repo.get(plantilla_id)
        if plantilla is None or plantilla.deleted_at is not None:
            raise NoEncontrado("plantilla de encuesta no encontrada")
        return plantilla

    sucursal = session.get(Sucursal, sucursal_id)
    if sucursal is None:
        raise NoEncontrado("sucursal de la venta no encontrada")
    plantilla = repo.activa_de_empresa(sucursal.empresa_id)
    if plantilla is None:
        raise ReglaNegocio(
            "no hay plantilla de encuesta activa para la empresa; hay que "
            "crear el guion antes de encuestar"
        )
    return plantilla


def _resolver_destino(session: Session, cliente_id: uuid.UUID, canal: str) -> str | None:
    if canal not in CANALES_CON_DESTINO:
        return None
    contacto = contacto_de_cliente(session, cliente_id)
    telefono = whatsapp.normalizar_telefono((contacto or {}).get("telefono", ""))
    if not telefono:
        raise ReglaNegocio(
            "el cliente no tiene teléfono registrado; no se le puede enviar la "
            "encuesta por WhatsApp"
        )
    return telefono


def _pregunta_actual(
    session: Session, encuesta: EncuestaSatisfaccion
) -> EncuestaPregunta:
    pregunta = pregunta_actual(session, encuesta)
    if pregunta is None:
        raise Conflicto("la encuesta no tiene pregunta pendiente")
    return pregunta


def _siguiente(
    session: Session,
    encuesta: EncuestaSatisfaccion,
    nodo: encuesta_flujo.Nodo,
    valor: str,
) -> EncuestaPregunta | None:
    codigo = encuesta_flujo.siguiente_codigo(nodo, valor)
    if codigo is None:
        return None
    return EncuestaPlantillaRepo(session).pregunta_por_codigo(
        encuesta.plantilla_id, codigo
    )


def _cerrar(session: Session, encuesta: EncuestaSatisfaccion) -> None:
    encuesta.estado = "respondida"
    encuesta.fecha_respuesta = datetime.now(UTC)
    event_bus.publish(
        "marketing.encuesta_respondida",
        {
            "encuesta_id": str(encuesta.id),
            "venta_id": str(encuesta.venta_id),
            "cliente_id": str(encuesta.cliente_id),
            "puntaje": encuesta.puntaje,
            "canal": encuesta.canal,
        },
        session=session,
    )


def _responder_sin_guion(
    session: Session, encuesta: EncuestaSatisfaccion, valor: str
) -> None:
    """Encuestas anteriores al guion (`plantilla_id` NULL): el valor es el
    puntaje suelto y ahí termina. No hay nodos que recorrer."""
    if not valor.strip().isdigit() or not encuesta_flujo.puntaje_valido(
        int(valor.strip())
    ):
        raise ReglaNegocio(
            f"puntaje fuera de rango ({encuesta_flujo.PUNTAJE_MIN}-"
            f"{encuesta_flujo.PUNTAJE_MAX})"
        )
    encuesta.puntaje = int(valor.strip())
    _cerrar(session, encuesta)
    session.flush()
    return None


def _ayuda(pregunta: EncuestaPregunta, nodo: encuesta_flujo.Nodo) -> str:
    aceptados = encuesta_flujo.valores_aceptados(nodo)
    if aceptados:
        return f"respuesta no válida para '{pregunta.codigo}': se espera {' / '.join(aceptados)}"
    return f"respuesta vacía para '{pregunta.codigo}'"


def _encuesta(session: Session, encuesta_id: uuid.UUID) -> EncuestaSatisfaccion:
    encuesta = EncuestaRepo(session).get(encuesta_id)
    if encuesta is None:
        raise NoEncontrado("encuesta no encontrada")
    return encuesta
