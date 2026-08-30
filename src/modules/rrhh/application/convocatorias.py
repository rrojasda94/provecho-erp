"""Casos de uso de `convocatoria`: requisición aprobada (borrador) →
publicación → cierre, y el tablero de contratación que cuelga de ella."""

import secrets
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import Convocatoria
from src.modules.rrhh.infrastructure.repositories import ConvocatoriaRepo, PostulanteRepo
from src.modules.users.infrastructure.models import Empresa


def crear_convocatoria(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    puesto: str,
    motivo: str,
    sucursal_id: uuid.UUID | None = None,
    perfil_puesto: str | None = None,
    vacantes: int = 1,
    jornada_horas_semana: Decimal | None = None,
    remuneracion_min: Decimal | None = None,
    remuneracion_max: Decimal | None = None,
    fecha_objetivo: date | None = None,
    fecha_limite: date | None = None,
) -> Convocatoria:
    if motivo not in rules.MOTIVOS_CONVOCATORIA:
        raise ReglaNegocio(f"motivo inválido: {motivo}")
    if vacantes < 1:
        raise ReglaNegocio("vacantes debe ser al menos 1")
    if (
        remuneracion_min is not None
        and remuneracion_max is not None
        and remuneracion_min > remuneracion_max
    ):
        raise ReglaNegocio("remuneracion_min no puede superar a remuneracion_max")
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")

    return ConvocatoriaRepo(session).add(
        Convocatoria(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            puesto=puesto,
            motivo=motivo,
            perfil_puesto=perfil_puesto,
            vacantes=vacantes,
            jornada_horas_semana=jornada_horas_semana,
            remuneracion_min=remuneracion_min,
            remuneracion_max=remuneracion_max,
            fecha_objetivo=fecha_objetivo,
            fecha_limite=fecha_limite,
        )
    )


def publicar_convocatoria(
    session: Session,
    convocatoria_id: uuid.UUID,
    *,
    fecha_publicacion: date,
    perfil_puesto: str | None = None,
) -> Convocatoria:
    """Publicar genera el token del formulario público: antes de esto la
    convocatoria no puede recibir postulaciones."""
    convocatoria = ConvocatoriaRepo(session).get(convocatoria_id)
    if convocatoria is None:
        raise NoEncontrado("convocatoria no encontrada")
    if perfil_puesto is not None:
        convocatoria.perfil_puesto = perfil_puesto
    if convocatoria.estado != "borrador":
        raise Conflicto(f"convocatoria está {convocatoria.estado}; no admite publicación")
    if not rules.puede_publicar_convocatoria(convocatoria.estado, convocatoria.perfil_puesto):
        raise ReglaNegocio(
            "no se publica una convocatoria sin perfil de puesto aprobado (RN-RRHH-013)"
        )
    convocatoria.estado = "publicada"
    convocatoria.fecha_publicacion = fecha_publicacion
    convocatoria.token_publico = secrets.token_urlsafe(32)
    return convocatoria


def cerrar_convocatoria(session: Session, convocatoria_id: uuid.UUID) -> Convocatoria:
    """Cerrar retira el token: el formulario deja de aceptar postulaciones,
    pero los postulantes ya recibidos siguen avanzando en el tablero."""
    convocatoria = ConvocatoriaRepo(session).get(convocatoria_id)
    if convocatoria is None:
        raise NoEncontrado("convocatoria no encontrada")
    if convocatoria.estado == "cerrada":
        raise Conflicto("convocatoria ya está cerrada")
    convocatoria.estado = "cerrada"
    convocatoria.token_publico = None
    return convocatoria


def publicada_por_token(session: Session, token: str, hoy: date) -> Convocatoria:
    """La convocatoria detrás del token del formulario público.

    El token es lo único que autoriza a leerla y a escribirle, y por eso solo
    existe mientras está publicada: `publicar_convocatoria` lo genera y
    `cerrar_convocatoria` lo retira. Vive acá y no en `postulantes` porque
    ahora lo usan los dos lados del formulario —la página que lo dibuja y el
    envío que lo recibe— y la regla de cuándo una convocatoria sigue abierta
    se escribe una sola vez.
    """
    convocatoria = ConvocatoriaRepo(session).get_por_token(token)
    if convocatoria is None or convocatoria.estado != "publicada":
        raise NoEncontrado("convocatoria no encontrada o cerrada")
    if convocatoria.fecha_limite is not None and hoy > convocatoria.fecha_limite:
        raise Conflicto("la convocatoria cerró su fecha límite")
    return convocatoria


def listar_convocatorias(
    session: Session, empresa_id: uuid.UUID | None = None, estado: str | None = None
) -> list[Convocatoria]:
    return ConvocatoriaRepo(session).list(empresa_id, estado)


def tablero(session: Session, convocatoria_id: uuid.UUID) -> list[dict]:
    """Postulantes agrupados por columna, en el orden del proceso. El orden
    de las columnas sale de acá y no se replica en el cliente."""
    postulantes = PostulanteRepo(session).list(convocatoria_id=convocatoria_id)
    columnas = [*rules.ETAPAS_POSTULANTE, rules.ESTADO_DESCARTADO]
    por_estado: dict[str, list] = {columna: [] for columna in columnas}
    for postulante in postulantes:
        por_estado[postulante.estado].append(postulante)
    return [{"estado": columna, "postulantes": por_estado[columna]} for columna in columnas]
