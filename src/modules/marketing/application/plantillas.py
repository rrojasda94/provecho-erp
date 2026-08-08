"""Casos de uso de la plantilla de encuesta: escribir el guion y activarlo.

El guion se valida entero antes de guardarse (`domain.encuesta_flujo.
plantilla_coherente`): un salto a un nodo inexistente o un ciclo no rompen
nada al guardar y sí dejan al cliente esperando una pregunta que nunca llega
—o recibiéndolas para siempre—, y a esa altura ya no hay a quién avisarle.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.marketing.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.marketing.domain import encuesta_flujo
from src.modules.marketing.infrastructure.models import EncuestaPlantilla, EncuestaPregunta
from src.modules.marketing.infrastructure.repositories import EncuestaPlantillaRepo
from src.modules.users.infrastructure.models import Marca


def a_nodo(pregunta: EncuestaPregunta) -> encuesta_flujo.Nodo:
    """Del modelo al dato puro que entiende el dominio."""
    return encuesta_flujo.Nodo(
        codigo=pregunta.codigo,
        tipo=pregunta.tipo,
        opciones=tuple(o["valor"] for o in (pregunta.opciones or [])),
        siguiente_codigo=pregunta.siguiente_codigo,
        saltos=dict(pregunta.saltos or {}),
        obligatoria=pregunta.obligatoria,
    )


def crear_plantilla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombre: str,
    saludo: str,
    preguntas: list[dict],
    creado_por: uuid.UUID,
    despedida: str = "¡Gracias por responder!",
    marca_id: uuid.UUID | None = None,
    activa: bool = False,
) -> EncuestaPlantilla:
    if marca_id is not None and session.get(Marca, marca_id) is None:
        raise NoEncontrado(f"marca {marca_id} no encontrada")
    _exigir_guion_coherente(preguntas)

    repo = EncuestaPlantillaRepo(session)
    plantilla = repo.add(
        EncuestaPlantilla(
            empresa_id=empresa_id,
            marca_id=marca_id,
            nombre=nombre,
            saludo=saludo,
            despedida=despedida,
            activa=False,
            creado_por=creado_por,
        )
    )
    for orden, datos in enumerate(preguntas, start=1):
        session.add(
            EncuestaPregunta(
                plantilla_id=plantilla.id,
                codigo=datos["codigo"],
                orden=orden,
                texto=datos["texto"],
                tipo=datos["tipo"],
                opciones=datos.get("opciones"),
                siguiente_codigo=datos.get("siguiente_codigo"),
                saltos=datos.get("saltos"),
                es_puntaje=datos.get("es_puntaje", False),
                obligatoria=datos.get("obligatoria", True),
            )
        )
    session.flush()
    if activa:
        activar(session, plantilla.id)
    return plantilla


def activar(session: Session, plantilla_id: uuid.UUID) -> EncuestaPlantilla:
    """Una activa por empresa: activar la nueva desactiva la anterior.

    Dos guiones vivos a la vez parten la serie histórica en dos mitades que
    no se pueden comparar, y nadie se entera hasta que el reporte mensual no
    cuadra.
    """
    repo = EncuestaPlantillaRepo(session)
    plantilla = repo.get(plantilla_id)
    if plantilla is None or plantilla.deleted_at is not None:
        raise NoEncontrado("plantilla de encuesta no encontrada")
    if not repo.preguntas_de(plantilla_id):
        raise Conflicto("la plantilla no tiene preguntas; no se puede activar")
    for otra in repo.activas_de_empresa(plantilla.empresa_id):
        otra.activa = False
    plantilla.activa = True
    session.flush()
    return plantilla


def primera_pregunta(session: Session, plantilla_id: uuid.UUID) -> EncuestaPregunta | None:
    preguntas = EncuestaPlantillaRepo(session).preguntas_de(plantilla_id)
    return preguntas[0] if preguntas else None


def _exigir_guion_coherente(preguntas: list[dict]) -> None:
    nodos = [
        encuesta_flujo.Nodo(
            codigo=p.get("codigo", ""),
            tipo=p.get("tipo", "texto"),
            opciones=tuple(o["valor"] for o in (p.get("opciones") or [])),
            siguiente_codigo=p.get("siguiente_codigo"),
            saltos=dict(p.get("saltos") or {}),
            obligatoria=p.get("obligatoria", True),
        )
        for p in preguntas
    ]
    problemas = encuesta_flujo.plantilla_coherente(nodos)
    if problemas:
        raise ReglaNegocio("guion inválido: " + "; ".join(problemas))
    if sum(1 for p in preguntas if p.get("es_puntaje")) > 1:
        raise ReglaNegocio("solo una pregunta puede ser la del puntaje")
