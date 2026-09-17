"""Fotos del catálogo público: presign a S3 + registro del `Archivo`
(ADR-101). Mismo patrón que `assets.application.documentos.presignar_adjunto`
/`adjuntar`, con dos entidades (`producto`, `ingrediente`) en vez de una.

El binario nunca pasa por el backend: el cliente sube directo a la URL
prefirmada y solo después llama a `registrar` con la `url_storage`
resultante.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from src.modules.inventory.application.queries_publicas import articulo_resumen
from src.modules.sales.application.queries_publicas import marca_de_producto
from src.modules.storefront.application.errors import NoEncontrado, ReglaNegocio
from src.modules.storefront.domain.rules import (
    ENTIDADES_FOTO,
    MIME_FOTO,
    TAMANO_MAXIMO_FOTO_BYTES,
)
from src.shared.adjuntos import crear_archivo
from src.shared.integrations.storage import s3
from src.shared.models import Archivo


def _validar_entidad(session, entidad: str, entidad_id: uuid.UUID) -> None:
    """La foto tiene que colgar de algo que exista de verdad — sin esto,
    `entidad_id` es cualquier UUID que alguien mande."""
    if entidad == "producto":
        if marca_de_producto(session, entidad_id) is None:
            raise NoEncontrado("producto no encontrado")
    elif entidad == "ingrediente":
        if articulo_resumen(session, entidad_id) is None:
            raise NoEncontrado("insumo no encontrado")
    else:
        raise ReglaNegocio(f"entidad de foto desconocida: {entidad}")


def presignar(
    session, *, entidad: str, entidad_id: uuid.UUID, nombre: str, mime_type: str
) -> dict:
    _validar_entidad(session, entidad, entidad_id)
    if not mime_type.startswith(MIME_FOTO):
        raise ReglaNegocio(f"tipo de archivo no admitido para una foto: {mime_type}")
    if not s3.configurado():
        raise ReglaNegocio("el almacenamiento S3 no está configurado (variables S3_*)")
    clave = f"{ENTIDADES_FOTO[entidad]}/{entidad_id}/{uuid.uuid4()}-{nombre}"
    return {
        "upload_url": s3.presigned_put_url(clave, content_type=mime_type),
        "url_storage": s3.url_publica(clave),
    }


def registrar(
    session,
    *,
    entidad: str,
    entidad_id: uuid.UUID,
    nombre: str,
    mime_type: str,
    tamano_bytes: int,
    url_storage: str,
    subido_por: uuid.UUID,
) -> Archivo:
    _validar_entidad(session, entidad, entidad_id)
    return crear_archivo(
        session,
        nombre=nombre,
        mime_type=mime_type,
        tamano_bytes=tamano_bytes,
        url_storage=url_storage,
        entidad_tipo=ENTIDADES_FOTO[entidad],
        entidad_id=entidad_id,
        subido_por=subido_por,
        mime_permitidos=MIME_FOTO,
        tamano_maximo_bytes=TAMANO_MAXIMO_FOTO_BYTES,
    )


def listar(session, *, entidad: str, entidad_id: uuid.UUID) -> list[Archivo]:
    return list(
        session.scalars(
            select(Archivo)
            .where(
                Archivo.entidad_tipo == ENTIDADES_FOTO[entidad],
                Archivo.entidad_id == entidad_id,
                Archivo.deleted_at.is_(None),
            )
            .order_by(Archivo.created_at.desc())
        )
    )


def foto_principal_url(session, *, entidad: str, entidad_id: uuid.UUID) -> str | None:
    """La más reciente no borrada. `None` si la entidad no tiene ninguna —
    el sitio público muestra un placeholder en ese caso."""
    fotos = listar(session, entidad=entidad, entidad_id=entidad_id)
    return fotos[0].url_storage if fotos else None


def borrar(session, *, archivo_id: uuid.UUID) -> None:
    archivo = session.scalar(
        select(Archivo).where(Archivo.id == archivo_id, Archivo.deleted_at.is_(None))
    )
    if archivo is None:
        raise NoEncontrado("foto no encontrada")
    archivo.deleted_at = datetime.now(UTC)
