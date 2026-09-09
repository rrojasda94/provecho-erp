- **Dos mecanismos de evidencia para la misma regla, y ninguno llenaba al
  otro** (2026-09-09, bloque `feat/produccion-evidencia-como-archivo` del
  plan de deuda de producción, RN-PRD-015). `orden_produccion.
  evidencia_destruccion_url` era un string libre que quien completaba la
  orden tecleaba en el mismo `POST .../completar`, sin que nadie pudiera
  verificar que apuntara a algo real ni listar qué se subió; mientras tanto
  `reporte_escalamiento.evidencia_id` (ADR-036) ya era una FK a `archivo`
  con storage S3 real, pedida aparte al abrir el escalamiento. Ahora la
  evidencia se sube una sola vez, vía `POST /production/ordenes/{id}/
  evidencia`, como `Archivo` (`orden.evidencia_archivo_id`); `completar`
  con `no_conforme_desechado` exige que ya exista, y el mismo id viaja en
  `production.no_conformidad_detectada.evidencia_id` para que
  `reports.application.escalamientos.abrir` lo use como default de
  `reporte_escalamiento.evidencia_id` — el usuario no la vuelve a pegar a
  mano. Migración con datos: toda `evidencia_destruccion_url` existente se
  convierte en `Archivo` antes de borrar la columna vieja.
- **La validación de MIME/tamaño de un adjunto solo existía en
  `marketing`** (mismo bloque). Extraída a `src/shared/adjuntos.py`
  (`crear_archivo`, con MIME permitidos y tamaño máximo por módulo);
  `marketing.application.adjuntos.adjuntar` y el nuevo `production.
  application.evidencia.adjuntar_evidencia` la reusan en vez de cada uno
  con su propia copia.
