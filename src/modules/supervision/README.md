# Módulo `supervision` — Tareas de apertura/cierre, checklist y foto

## Objetivo

Programar, generar y ejecutar las tareas de apertura y cierre de sucursal
(los SOP de `docs/diagrams/Procesos/Operaciones/`), organizadas por
categoría y frecuencia, con checklist y evidencia fotográfica opcional. El
supervisor programa; el trabajador de línea solo ve y ejecuta lo que le
fue asignado. Al cerrar la jornada se emite un informe diario por
sucursal, que entra al catálogo centralizado del módulo `reports` (ADR-033)
y se escala con el mecanismo ya existente (ADR-036).

Detalle de diseño: ADR-101. Reglas: `docs/domain/business-rules.md`
§Supervisión (RN-SUP-001..008). Modelo de datos:
`docs/architecture/data-model.md` §15.

## Entidades

`categoria_tarea` (catálogo libre por empresa), `tarea_plantilla` (qué se
hace, en qué momento —apertura/cierre—, con qué frecuencia
—diaria/interdiaria/semanal/mensual— y con qué checklist; alcanza a una
sucursal o a toda una marca), `tarea_instancia` (la tarea del día, generada
de una plantilla o creada a mano; lleva el checklist, la foto comprimida y
su fecha EXIF, y el estado `pendiente`\|`completada`\|`vencida`),
`informe_diario` (el resumen de una sucursal al cerrar la jornada — es la
entidad a la que apunta el reporte emitido).

## Casos de uso

- `categorias.py` / `plantillas.py`: CRUD de categorías y plantillas.
- `generacion.py`: `generar_instancias` (idempotente por
  `(plantilla_id, sucursal_id, fecha)`) fabrica la tarea del día por cada
  sucursal cuando su plantilla `toca_hoy`; `crear_tarea_manual` para un
  imprevisto que no amerita una plantilla; `asignar` reparte una tarea.
- `tareas.py`: `marcar_item`, `adjuntar_foto`, `completar` — solo el
  trabajador asignado (`domain.rules.puede_ejecutar`).
- `fotos.py`: comprime con Pillow y lee el EXIF `DateTimeOriginal` antes de
  tirarlo — la fecha de captura no la declara el cliente.
- `informes.py`: `generar_informe` vence lo pendiente y publica
  `supervision.informe_diario_generado`.
- `tasks.py`: tres barridos de Celery — generar el día, cerrar jornadas
  vencidas, purgar fotos viejas.

## Eventos

| Evento | Consumidores | Payload |
|---|---|---|
| `supervision.informe_diario_generado` | `reports` (catálogo, área Gerencia) | informe_id, sucursal_id, fecha, total, completadas, vencidas, fotos_invalidas |

No consume eventos de otro módulo — sin `application/listeners.py`.

## Endpoints (`/api/v1/supervision`)

| Método | Ruta | Permiso |
|---|---|---|
| GET/POST/PATCH | `/categorias[/{id}]` | `supervision.leer` / `gestionar` |
| GET/POST/PATCH/DELETE | `/plantillas[/{id}]` | `supervision.leer` / `gestionar` (`DELETE` desactiva, no borra) |
| GET | `/tareas?sucursal_id&fecha` | `supervision.leer` |
| GET | `/tareas/mias?fecha` | `supervision.ejecutar` — solo las asignadas al actor |
| POST | `/tareas` (manual), `/tareas/generar` | `supervision.gestionar` |
| PATCH | `/tareas/{id}/asignar` | `supervision.gestionar` |
| PATCH | `/tareas/{id}/checklist/{indice}` | `supervision.ejecutar` + ser el asignado |
| POST | `/tareas/{id}/foto` (multipart) | `supervision.ejecutar` + ser el asignado |
| POST | `/tareas/{id}/completar` | `supervision.ejecutar` + ser el asignado |
| GET | `/tareas/{id}`, `/tareas/{id}/foto` | `supervision.leer` o ser el asignado |
| GET/POST | `/informes[/generar]` | `supervision.leer` / `gestionar` |

## Reglas clave

RN-SUP-001..008 en `docs/domain/business-rules.md`. Resumen: una plantilla
alcanza a una sucursal o a una marca entera, nunca a ninguna de las dos
(RN-SUP-001); el `orden` se puede repetir, son tareas en paralelo
(RN-SUP-002); solo el asignado ejecuta su tarea (RN-SUP-003); completar
exige checklist completo y foto si la tarea la pide, con la hora de
finalización del servidor (RN-SUP-004); la foto se comprime y se le lee el
EXIF en el servidor (RN-SUP-005); una foto sin EXIF o fuera de ventana no
bloquea completar, solo se marca para revisión (RN-SUP-006); al cerrar la
jornada, lo pendiente pasa a vencido (RN-SUP-007); la foto se purga a los
30 días, la fila se queda (RN-SUP-008).

## Dependencias

Lee `users.infrastructure.models` (Sucursal, Marca, Empresa, Usuario) igual
que el resto de módulos operativos — nunca su dominio. Publica a `reports`
por evento, nunca lo importa. Usa `src.shared.auditoria` (acto de
autoridad: completar una tarea) y `src.shared.fechas` (instante del
servidor, zona del negocio).

## Deuda declarada

Ver `docs/roadmap/deuda/modulo-supervision.md`: hora de cierre de jornada
por empresa (hoy valor semilla), rotación automática de responsable por
turno, frecuencias quincenal/semestral, SOP de cierre de local propiamente
dicho.
