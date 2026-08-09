"""Adjuntos de una pieza de contenido: el arte, no solo el título.

`pieza_contenido` guardaba título, canal, fecha y métricas — todo menos la
pieza. Un calendario de contenido sin el arte obliga a abrir otra carpeta
para saber qué se publica el jueves, y ahí es donde se publica la versión
vieja del banner.

Cuelga de `archivo` (`src/shared/models/archivo.py`), que ya existe y ya es
polimórfico: crear storage propio para marketing habría sido una segunda
tabla de archivos con las mismas columnas. El ERP guarda el **vínculo y los
metadatos**, no el binario: el binario vive en S3 y quien lo sube habla
directo con el storage.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.marketing.application.errors import Conflicto, NoEncontrado
from src.modules.marketing.infrastructure.repositories import PiezaContenidoRepo
from src.shared.models import Archivo

ENTIDAD = "pieza_contenido"

# Lo que tiene sentido adjuntar a una pieza: arte, video, copy o el brief.
MIME_PERMITIDOS = (
    "image/",
    "video/",
    "audio/",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",
    "text/",
)
TAMANO_MAXIMO_BYTES = 100 * 1024 * 1024


def adjuntar(
    session: Session,
    pieza_id: uuid.UUID,
    *,
    nombre: str,
    mime_type: str,
    tamano_bytes: int,
    url_storage: str,
    subido_por: uuid.UUID,
) -> Archivo:
    pieza = PiezaContenidoRepo(session).get(pieza_id)
    if pieza is None:
        raise NoEncontrado("pieza de contenido no encontrada")
    if pieza.estado == "descartada":
        raise Conflicto("la pieza está descartada; no admite adjuntos")
    if not mime_type.startswith(MIME_PERMITIDOS):
        raise Conflicto(f"tipo de archivo no admitido para una pieza: {mime_type}")
    if tamano_bytes > TAMANO_MAXIMO_BYTES:
        raise Conflicto(
            f"el archivo supera el máximo de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB"
        )

    archivo = Archivo(
        nombre=nombre,
        extension=nombre.rsplit(".", 1)[-1][:10] if "." in nombre else "",
        mime_type=mime_type,
        tamano_bytes=tamano_bytes,
        url_storage=url_storage,
        origen="subido",
        entidad_tipo=ENTIDAD,
        entidad_id=pieza_id,
        subido_por=subido_por,
    )
    session.add(archivo)
    session.flush()
    return archivo


def listar(session: Session, pieza_id: uuid.UUID) -> list[Archivo]:
    return list(session.scalars(q_de_piezas([pieza_id])))


def q_de_piezas(pieza_ids: list[uuid.UUID]):
    return (
        select(Archivo)
        .where(
            Archivo.entidad_tipo == ENTIDAD,
            Archivo.entidad_id.in_(pieza_ids),
            Archivo.deleted_at.is_(None),
        )
        .order_by(Archivo.created_at)
    )


def conteo_por_pieza(session: Session, pieza_ids: list[uuid.UUID]) -> dict:
    """Cuántos adjuntos tiene cada pieza, de una sola consulta. El calendario
    muestra decenas de piezas: pedirle los adjuntos a cada una sería el
    problema N+1 con otro nombre."""
    if not pieza_ids:
        return {}
    conteo: dict[uuid.UUID, int] = {}
    for archivo in session.scalars(q_de_piezas(pieza_ids)):
        conteo[archivo.entidad_id] = conteo.get(archivo.entidad_id, 0) + 1
    return conteo


def quitar(session: Session, pieza_id: uuid.UUID, archivo_id: uuid.UUID) -> Archivo:
    """Borrado lógico. El arte de una pieza ya publicada es evidencia de qué
    se publicó: se saca de la vista, no de la historia."""
    archivo = session.get(Archivo, archivo_id)
    if (
        archivo is None
        or archivo.deleted_at is not None
        or archivo.entidad_tipo != ENTIDAD
        or archivo.entidad_id != pieza_id
    ):
        raise NoEncontrado("adjunto no encontrado")
    archivo.deleted_at = func.now()
    session.flush()
    return archivo
