"""S3 (o compatible): URLs prefirmadas de subida para adjuntos binarios.

Mismo bucket y credenciales que `src.backups.backup` (settings `s3_*`) — un
solo almacén externo para todo el ERP, distinto solo por prefijo de clave
(`backups/…` vs `documentos-vigencia/…`). `boto3` es dependencia opcional
(`[backups]`, ADR-007) y se importa acá adentro, no arriba: el que nunca
configura S3 ni sube adjuntos no paga el costo de cargarla.

El binario nunca pasa por acá ni por el backend: el cliente lo sube directo
al `upload_url` prefirmado (`PUT`), y solo después llama al endpoint que
guarda los metadatos (`Archivo`) con la `url_storage` resultante — mismo
criterio que `marketing.application.adjuntos` ya documentaba, ahora con una
forma real de conseguir esa URL en vez de que el cliente hable con S3 por
su cuenta.
"""

from src.config.settings import settings


class S3NoConfigurado(Exception):
    """Sin bucket o credenciales — no hay dónde subir el archivo."""


def configurado() -> bool:
    return bool(settings.s3_bucket and settings.s3_access_key and settings.s3_secret_key)


def _cliente():
    try:
        import boto3
    except ImportError as e:
        raise S3NoConfigurado('falta boto3: pip install -e ".[backups]"') from e
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def presigned_put_url(clave: str, *, content_type: str, expira_segundos: int = 300) -> str:
    """URL prefirmada de un único `PUT` a `clave`, válida `expira_segundos`.

    `content_type` va firmado: el cliente tiene que subir con el mismo
    header o S3 rechaza la firma — es lo que evita que alguien use la URL
    para subir algo distinto de lo que se declaró.
    """
    if not configurado():
        raise S3NoConfigurado("S3 no está configurado (faltan variables S3_*)")
    return _cliente().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": clave, "ContentType": content_type},
        ExpiresIn=expira_segundos,
    )


def url_publica(clave: str) -> str:
    """La URL del objeto una vez subido — lo que se guarda en
    `Archivo.url_storage`. No valida que el objeto exista: eso lo confirma
    el propio `PUT` del cliente."""
    if settings.s3_endpoint:
        return f"{settings.s3_endpoint.rstrip('/')}/{settings.s3_bucket}/{clave}"
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{clave}"
