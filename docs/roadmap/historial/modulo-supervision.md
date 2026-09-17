# Historial — Módulo supervision

Bitácora narrativa completa. El estado vigente y el resumen ejecutivo
viven en [`ROADMAP.md`](../../../ROADMAP.md) → Estado por módulo.

## 2026-09-17 — Slice core (ADR-102)

Módulo nuevo: programación de tareas de apertura y cierre de sucursal por
categoría y frecuencia, con checklist y evidencia fotográfica opcional.
Cierra el hueco entre los SOP de `docs/diagrams/Procesos/Operaciones/`
(tres de Apertura-Sucursal, dieciséis de Limpieza — todos piden checklist
firmado y varios piden foto "subida al ERP") y el código: hasta hoy el
único checklist operativo era `checklist_inocuidad_turno` de `production`,
que es de turno de cocina, no de local.

**Modelo**: `categoria_tarea` (catálogo libre por empresa),
`tarea_plantilla` (momento apertura/cierre, orden repetible para tareas en
paralelo, frecuencia diaria/interdiaria/semanal/mensual, alcanza a una
sucursal o a toda una marca), `tarea_instancia` (la tarea del día,
idempotente por `(plantilla_id, sucursal_id, fecha)`, con foto
`LargeBinary` diferida y su fecha EXIF), `informe_diario` (resumen de
cierre de jornada por sucursal). Migración `d518f6efa2ce`.

**Fotos en Postgres, no S3** — el servidor necesita abrir la imagen para
comprimirla y leer su EXIF `DateTimeOriginal` antes de que el cliente
pueda editarlo, cosa que una subida directa a S3 con URL prefirmada no
permite. Pillow entra como dependencia de la API (decisión explícita: el
proyecto lo evitaba a propósito por el QR del comprobante, que usa
`segno`). Una foto sin EXIF o fuera de la ventana de tolerancia
(`supervision_foto_tolerancia_minutos`) no bloquea completar la tarea:
queda marcada `foto_valida=false`/`null` para que el supervisor la revise
(RN-SUP-006, mismo criterio que RN-SUC-006). Purga a los
`supervision_foto_retencion_dias` (30 por defecto) vía Celery, mismo
patrón que `rrhh.purgar_fotos_de_marcacion` y `delivery.purgar_evidencias`.

**Asignación**: la plantilla lleva un responsable opcional que la
instancia hereda; sin responsable, nace "sin asignar" y el supervisor la
reparte desde el tablero (`PATCH /tareas/{id}/asignar`). Solo el asignado
puede marcar el checklist, subir la foto o completar (RN-SUP-003) — el
trabajador de línea solo ve `GET /tareas/mias`.

**Cierre e informe**: barrido de Celery cada 15 min
(`supervision.cerrar_jornadas_vencidas`, mismo criterio que
`production.generar_reportes_de_jornada_vencidos` porque la hora de cierre
es configurable) marca lo `pendiente` como `vencida` y genera
`informe_diario`. Se emite como `supervision.informe_diario_generado` al
catálogo de `reports` (ADR-033) — el supervisor lo escala con la cadena
supervisor→comercial→gerencia ya existente (ADR-036), sin mecanismo
propio.

**Permisos**: `supervision.gestionar` (supervisor), `supervision.leer`
(supervisor + jefe_cocina), `supervision.ejecutar` (cajero, cocinero,
despachador, almacenero, jefe_cocina).

Deuda declarada: `docs/roadmap/deuda/modulo-supervision.md` (hora de
cierre por empresa, rotación automática de responsable, frecuencias
quincenal/semestral, SOP de cierre de local inexistente).
