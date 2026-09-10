"""Evidencia de destrucción de una orden desechada (RN-PRD-015).

Hasta `feat/produccion-evidencia-como-archivo` (2026-09-09),
`evidencia_destruccion_url` era un string libre que quien completaba la
orden tecleaba en el mismo `POST .../completar` — sin verificar que
apuntara a algo real, y sin que nadie más pudiera listar qué se subió. Ahora
la evidencia se registra aparte, como `Archivo` (`src/shared/adjuntos.py`,
mismo mecanismo que `marketing.application.adjuntos`): `completar_orden_
produccion` solo exige que `orden.evidencia_archivo_id` esté seteado, no
vuelve a validar la URL.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.production.application.errors import NoEncontrado
from src.modules.production.infrastructure.repositories import OrdenProduccionRepo
from src.modules.users.infrastructure.models import Almacen
from src.shared import adjuntos, auditoria
from src.shared.models import Archivo

ENTIDAD = "orden_produccion"
# Evidencia de destrucción: una foto o un video del hecho, no un documento.
MIME_PERMITIDOS = ("image/", "video/")
TAMANO_MAXIMO_BYTES = 50 * 1024 * 1024


def adjuntar_evidencia(
    session: Session,
    orden_id: uuid.UUID,
    *,
    nombre: str,
    mime_type: str,
    tamano_bytes: int,
    url_storage: str,
    subido_por: uuid.UUID,
    ip: str | None = None,
) -> Archivo:
    orden = OrdenProduccionRepo(session).get(orden_id)
    if orden is None:
        raise NoEncontrado("orden de producción no encontrada")
    archivo = adjuntos.crear_archivo(
        session,
        nombre=nombre,
        mime_type=mime_type,
        tamano_bytes=tamano_bytes,
        url_storage=url_storage,
        entidad_tipo=ENTIDAD,
        entidad_id=orden_id,
        subido_por=subido_por,
        mime_permitidos=MIME_PERMITIDOS,
        tamano_maximo_bytes=TAMANO_MAXIMO_BYTES,
    )
    # Última evidencia adjuntada = la vigente: RN-PRD-015 no pide historial,
    # pide que exista una al cerrar en desecho (`completar_orden_produccion`
    # solo mira este campo).
    orden.evidencia_archivo_id = archivo.id
    almacen = session.get(Almacen, orden.almacen_id)
    auditoria.registrar(
        session,
        usuario_id=subido_por,
        entidad="orden_produccion",
        accion="adjuntar_evidencia",
        entidad_id=orden.id,
        datos_despues={"archivo_id": str(archivo.id), "nombre": nombre},
        empresa_id=almacen.empresa_id if almacen else None,
        ip=ip,
    )
    return archivo
