"""Documento con fecha de vencimiento (permiso, certificado, licencia) de un
activo, sucursal, empresa o trabajador."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.assets.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.assets.domain import rules
from src.modules.assets.infrastructure.models import DocumentoVigencia
from src.modules.assets.infrastructure.repositories import DocumentoVigenciaRepo
from src.shared.integrations.storage import s3
from src.shared.models import Archivo

ENTIDAD_ADJUNTO = "documento_vigencia"
MIME_PERMITIDOS = ("image/", "application/pdf")
TAMANO_MAXIMO_BYTES = 20 * 1024 * 1024


def crear_documento(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    sujeto_tipo: str,
    sujeto_id: uuid.UUID,
    tipo_documento: str,
    fecha_vencimiento: date,
    numero: str | None = None,
    emisor: str | None = None,
    fecha_emision: date | None = None,
    dias_aviso: int = rules.DIAS_AVISO_DOCUMENTO_DEFECTO,
    notas: str | None = None,
) -> DocumentoVigencia:
    if tipo_documento not in rules.TIPOS_DOCUMENTO:
        raise ReglaNegocio(f"tipo de documento inválido: {tipo_documento}")
    if fecha_emision is not None and fecha_emision > fecha_vencimiento:
        raise ReglaNegocio("la fecha de emisión no puede ser posterior al vencimiento")
    return DocumentoVigenciaRepo(session).add(
        DocumentoVigencia(
            empresa_id=empresa_id,
            sujeto_tipo=sujeto_tipo,
            sujeto_id=sujeto_id,
            tipo_documento=tipo_documento,
            numero=numero,
            emisor=emisor,
            fecha_emision=fecha_emision,
            fecha_vencimiento=fecha_vencimiento,
            dias_aviso=dias_aviso,
            notas=notas,
        )
    )


def editar_documento(
    session: Session,
    documento_id: uuid.UUID,
    *,
    numero: str | None = None,
    emisor: str | None = None,
    fecha_vencimiento: date | None = None,
    dias_aviso: int | None = None,
    notas: str | None = None,
) -> DocumentoVigencia:
    documento = DocumentoVigenciaRepo(session).get(documento_id)
    if documento is None:
        raise NoEncontrado("documento no encontrado")
    for campo, valor in (
        ("numero", numero),
        ("emisor", emisor),
        ("fecha_vencimiento", fecha_vencimiento),
        ("dias_aviso", dias_aviso),
        ("notas", notas),
    ):
        if valor is not None:
            setattr(documento, campo, valor)
    return documento


def renovar_documento(
    session: Session,
    documento: DocumentoVigencia,
    *,
    fecha_vencimiento: date,
    numero: str | None = None,
    emisor: str | None = None,
    fecha_emision: date | None = None,
) -> DocumentoVigencia:
    """Un documento renovado no se edita: nace uno nuevo y el viejo queda
    encadenado (`renovado_por_id`), porque una inspección puede pedir ver el
    vencido de hace un año igual que el vigente de hoy."""
    if documento.renovado_por_id is not None:
        raise Conflicto("este documento ya fue renovado")
    nuevo = crear_documento(
        session,
        empresa_id=documento.empresa_id,
        sujeto_tipo=documento.sujeto_tipo,
        sujeto_id=documento.sujeto_id,
        tipo_documento=documento.tipo_documento,
        fecha_vencimiento=fecha_vencimiento,
        numero=numero or documento.numero,
        emisor=emisor or documento.emisor,
        fecha_emision=fecha_emision,
        dias_aviso=documento.dias_aviso,
    )
    documento.renovado_por_id = nuevo.id
    return nuevo


def presignar_adjunto(
    session: Session,
    documento_id: uuid.UUID,
    *,
    nombre: str,
    mime_type: str,
) -> dict:
    """URL prefirmada para que el cliente suba el binario directo a S3
    (`s3.presigned_put_url`); el metadato se guarda después, en `adjuntar`,
    con la `url_storage` que esta función ya devuelve."""
    if DocumentoVigenciaRepo(session).get(documento_id) is None:
        raise NoEncontrado("documento no encontrado")
    if not mime_type.startswith(MIME_PERMITIDOS):
        raise Conflicto(f"tipo de archivo no admitido para un documento: {mime_type}")
    if not s3.configurado():
        raise ReglaNegocio("el almacenamiento S3 no está configurado (variables S3_*)")
    clave = f"{ENTIDAD_ADJUNTO}/{documento_id}/{uuid.uuid4()}-{nombre}"
    return {
        "upload_url": s3.presigned_put_url(clave, content_type=mime_type),
        "url_storage": s3.url_publica(clave),
    }


def adjuntar(
    session: Session,
    documento_id: uuid.UUID,
    *,
    nombre: str,
    mime_type: str,
    tamano_bytes: int,
    url_storage: str,
    subido_por: uuid.UUID,
) -> Archivo:
    documento = DocumentoVigenciaRepo(session).get(documento_id)
    if documento is None:
        raise NoEncontrado("documento no encontrado")
    if not mime_type.startswith(MIME_PERMITIDOS):
        raise Conflicto(f"tipo de archivo no admitido para un documento: {mime_type}")
    if tamano_bytes > TAMANO_MAXIMO_BYTES:
        raise Conflicto(f"el archivo supera el máximo de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB")
    archivo = Archivo(
        nombre=nombre,
        extension=nombre.rsplit(".", 1)[-1][:10] if "." in nombre else "",
        mime_type=mime_type,
        tamano_bytes=tamano_bytes,
        url_storage=url_storage,
        origen="subido",
        entidad_tipo=ENTIDAD_ADJUNTO,
        entidad_id=documento_id,
        subido_por=subido_por,
    )
    session.add(archivo)
    session.flush()
    return archivo


def listar_adjuntos(session: Session, documento_id: uuid.UUID) -> list[Archivo]:
    return list(
        session.scalars(
            select(Archivo)
            .where(
                Archivo.entidad_tipo == ENTIDAD_ADJUNTO,
                Archivo.entidad_id == documento_id,
                Archivo.deleted_at.is_(None),
            )
            .order_by(Archivo.created_at)
        )
    )


def q_documentos(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    sujeto_tipo: str | None = None,
    sujeto_id: uuid.UUID | None = None,
):
    return DocumentoVigenciaRepo(session).q_list(
        empresa_id, sujeto_tipo=sujeto_tipo, sujeto_id=sujeto_id
    )


def q_de_sujeto(session: Session, sujeto_tipo: str, sujeto_id: uuid.UUID):
    return DocumentoVigenciaRepo(session).q_de_sujeto(sujeto_tipo, sujeto_id)
