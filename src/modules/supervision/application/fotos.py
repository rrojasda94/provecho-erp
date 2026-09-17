"""Procesamiento de la foto de evidencia: lee la fecha EXIF antes de que se
pierda, comprime y descarta el resto del metadato.

Pillow es la única dependencia de imagen del proyecto (`pyproject.toml`
evitaba una a propósito por el QR de `segno`, pero comprimir y leer EXIF en
el servidor —no confiar la fecha de captura al cliente— la justifica acá).

La foto nunca bloquea completar la tarea por sí sola (RN-SUP-006): si no se
puede procesar, se guarda igual sin validar la fecha.
"""

import io
from datetime import UTC, datetime

from PIL import ExifTags, Image, ImageOps

from src.shared import fechas

# Formato exacto que EXIF usa para `DateTimeOriginal`.
_FORMATO_EXIF = "%Y:%m:%d %H:%M:%S"
_TAG_FECHA_ORIGINAL = next(
    codigo for codigo, nombre in ExifTags.TAGS.items() if nombre == "DateTimeOriginal"
)

# Lado más largo tras el redimensionado y calidad JPEG — de sobra para
# revisar un checklist en pantalla, lejos de lo que pesa una foto de cámara.
LADO_MAXIMO_PX = 1280
CALIDAD_JPEG = 70
TAMANO_MAXIMO_ENTRADA_BYTES = 10 * 1024 * 1024
MIME_PERMITIDOS = ("image/",)


def _fecha_exif(imagen: Image.Image) -> datetime | None:
    exif = imagen.getexif()
    valor = exif.get(_TAG_FECHA_ORIGINAL)
    if not valor:
        return None
    try:
        naive = datetime.strptime(valor, _FORMATO_EXIF)
    except ValueError:
        return None
    # La cámara del celular del local no trae zona: se asume la hora del
    # negocio, que es donde se está tomando la foto. Se guarda en UTC
    # (`instante`, no fecha de calendario — `src/shared/fechas.py`) porque
    # SQLite devuelve el campo sin zona tras el viaje de ida y vuelta, con
    # los mismos dígitos: solo comparando en UTC en los dos extremos
    # (`domain/rules.py::foto_es_de_ahora`) el resultado no cambia según el
    # motor de base de datos.
    return naive.replace(tzinfo=fechas.zona()).astimezone(UTC)


def procesar(contenido: bytes) -> tuple[bytes, datetime | None]:
    """Devuelve `(jpeg_comprimido, fecha_de_captura)`.

    `fecha_de_captura` es `None` si la foto no traía `DateTimeOriginal` —
    frecuente en apps de cámara que no lo escriben, no es evidencia de nada.
    """
    with Image.open(io.BytesIO(contenido)) as imagen:
        tomada_at = _fecha_exif(imagen)
        # `exif_transpose` antes de tirar el EXIF: si no, una foto tomada en
        # vertical con el sensor de orientación se guarda de costado.
        imagen = ImageOps.exif_transpose(imagen).convert("RGB")
        imagen.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
        salida = io.BytesIO()
        imagen.save(salida, format="JPEG", quality=CALIDAD_JPEG)
        return salida.getvalue(), tomada_at
