"""Adjuntos genéricos: valida MIME/tamaño y crea el `Archivo` (S3) que
vincula un binario ya subido a cualquier entidad (RN-ARC-001/002).

Extraído de `marketing.application.adjuntos` (el primer módulo que adjuntó
algo) porque `production` necesita la misma validación para la evidencia de
destrucción de un desecho (RN-PRD-015). Cada módulo define **su propio**
juego de MIME permitidos y tamaño máximo —el arte de una pieza no es la foto
de un desecho—, pero crear el `Archivo` y rechazar lo que no cumple es la
misma cuenta en los dos: dos copias divergirían el día que alguien corrija
una y no la otra.

El ERP guarda el **vínculo y los metadatos**, no el binario: el binario vive
en S3 y quien lo sube habla directo con el storage.
"""

import uuid

from sqlalchemy.orm import Session

from src.shared.errors import Conflicto
from src.shared.models import Archivo


def crear_archivo(
    session: Session,
    *,
    nombre: str,
    mime_type: str,
    tamano_bytes: int,
    url_storage: str,
    entidad_tipo: str,
    entidad_id: uuid.UUID,
    subido_por: uuid.UUID,
    mime_permitidos: tuple[str, ...],
    tamano_maximo_bytes: int,
) -> Archivo:
    if not mime_type.startswith(mime_permitidos):
        raise Conflicto(f"tipo de archivo no admitido: {mime_type}")
    if tamano_bytes > tamano_maximo_bytes:
        raise Conflicto(
            f"el archivo supera el máximo de {tamano_maximo_bytes // (1024 * 1024)} MB"
        )
    archivo = Archivo(
        nombre=nombre,
        extension=nombre.rsplit(".", 1)[-1][:10] if "." in nombre else "",
        mime_type=mime_type,
        tamano_bytes=tamano_bytes,
        url_storage=url_storage,
        origen="subido",
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        subido_por=subido_por,
    )
    session.add(archivo)
    session.flush()
    return archivo
