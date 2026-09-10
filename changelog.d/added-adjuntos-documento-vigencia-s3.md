- **Adjuntos de `documento_vigencia` con subida binaria real a S3**
  (2026-09-09, RN-DOC-005). Hasta ahora `Archivo` solo guardaba metadata sin
  ninguna forma real de conseguir la URL — `POST
  /assets/documentos/{id}/adjuntos/presign-upload` genera una URL prefirmada
  de subida (`src/shared/integrations/storage/s3.py`, mismo bucket y
  credenciales que `src.backups.backup`, `boto3` sigue opcional `[backups]`,
  ADR-007) y el cliente sube el binario directo ahí antes de registrar el
  metadato. Frontend: diálogo de adjuntar en la pantalla de Documentos.
