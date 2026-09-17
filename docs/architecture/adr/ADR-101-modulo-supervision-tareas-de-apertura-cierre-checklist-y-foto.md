# ADR-101 — Módulo supervision: tareas de apertura/cierre, checklist y foto

- Estado: aceptado
- Fecha: 2026-09-17
- Contexto: `src/modules/supervision/`, `docs/diagrams/Procesos/Operaciones/`
  (Apertura-Sucursal, Limpieza)
- Relacionado: ADR-033/036 (emisión y distribución de reportes), ADR-097
  (CheckConstraint de todo Enum sin tipo nativo), RN-SUC-006, RN-SUP-001..008

## Contexto

Los SOP de `docs/diagrams/Procesos/Operaciones/` (tres de Apertura-Sucursal,
dieciséis de Limpieza) piden checklists firmados y, en varios, "evidencia
fotográfica subida al ERP" — pero hasta hoy nada de eso tenía pantalla. El
único checklist en código es `checklist_inocuidad_turno` de `production`,
que es de turno de cocina, no de apertura/cierre de local. El supervisor
programa manual o automáticamente qué se hace, cuándo y con qué frecuencia;
el trabajador de línea marca su checklist y sube la foto desde el celular;
el ERP valida esa foto sin confiar en lo que el cliente declare.

## Decisión

**Las fotos viven en Postgres (`LargeBinary` diferido), no en S3.** El
adaptador de S3 existe (`src/shared/integrations/storage/s3.py`) pero el
binario nunca pasa por el backend: el cliente sube directo con URL
prefirmada. Acá el servidor necesita **abrir** la foto para comprimirla y
leer su EXIF antes de que el cliente pueda editarlo — subir directo a S3
no permite ninguna de las dos cosas. Mismo patrón que la foto de marcación
de `rrhh` y la evidencia de entrega de `delivery`: columna diferida,
purgada por Celery a los `supervision_foto_retencion_dias` (30 por
defecto), la fila se queda.

**Pillow entra como dependencia de la API**, cosa que `pyproject.toml`
evitaba a propósito (el QR del comprobante usa `segno`, sin Pillow, para no
arrastrar una toolchain de imagen). La justificación es distinta acá: no se
trata de generar una imagen, sino de leer el EXIF `DateTimeOriginal` de una
que llega del cliente — sin eso, la fecha de la foto es lo que el cliente
diga, que es exactamente lo que había que dejar de confiar. El costo es
~3 MB extra en la imagen Docker de la API.

**La fecha EXIF nunca bloquea completar la tarea (RN-SUP-006).** Una foto
sin `DateTimeOriginal` (frecuente: muchas apps de cámara no lo escriben) o
con una fecha fuera de la ventana de tolerancia se guarda igual, marcada
`foto_valida=false` o `null`. La alternativa —rechazar la foto— convertiría
un dato de auditoría en un candado que un trabajador con la cámara mal
configurada no podría pasar nunca, por una causa que no depende de él.
Mismo criterio que RN-SUC-006 (el checklist de apertura es una meta
operativa, no un bloqueo automático): la meta es visibilidad para el
supervisor, no impedir la apertura.

**Asignación por plantilla, con responsable opcional y reasignación
diaria.** La plantilla puede llevar un `asignado_a` fijo, que la instancia
del día hereda; sin responsable, la instancia nace "sin asignar" y el
supervisor la reparte desde el tablero. La alternativa de asignar siempre a
mano todos los días fue descartada por el usuario: la mayoría de tareas
tiene un responsable estable (el que abre el salón, el que prende el
horno), y forzar la asignación diaria de todo sería trabajo repetido sin
ganar nada donde no hay rotación real de turno.

**El informe diario es una entidad propia de `supervision`, y el
escalamiento lo hace `reports`, no un mecanismo nuevo.** Al cerrar la
jornada de una sucursal (barrido cada 15 min, mismo criterio que
`production.generar_reportes_de_jornada_vencidos` porque la hora de cierre
es configurable), toda tarea `pendiente` pasa a `vencida` y se genera
`informe_diario`. Ese hecho se publica como
`supervision.informe_diario_generado` al catálogo de `reports` (ADR-033):
el supervisor lo escala con la cadena supervisor→comercial→gerencia que ya
existe (ADR-036), sin que este módulo tenga que reinventar destinatarios,
niveles ni auditoría de escalamiento.

**Un `orden` repetible, no una secuencia estricta.** Dos tareas de una
plantilla pueden compartir `orden` — se hacen en paralelo (encender las
luces mientras se trae lo de limpieza). El orden agrupa turnos de trabajo
dentro del momento (apertura/cierre), no impone una fila única que nadie
pidió.

**Una plantilla de marca genera una instancia por sucursal, y la
idempotencia de la generación diaria es por `(plantilla_id, sucursal_id,
fecha)`**, no solo `(plantilla_id, fecha)` — con la clave más corta, la
segunda sucursal de la marca se veía como "ya generada" por la primera y
se quedaba sin tarea. El índice único parcial (`plantilla_id IS NOT NULL`)
deja que una tarea manual (`plantilla_id` nulo) se repita el mismo día sin
chocar con nada.

## Consecuencias

- Nuevas reglas **RN-SUP-001..008** en `docs/domain/business-rules.md`.
- Deuda declarada (`docs/roadmap/deuda/modulo-supervision.md`): hora de
  cierre de jornada por empresa vía `parametro_empresa` (hoy valor
  semilla, igual que `production_hora_cierre_jornada` antes de su propio
  ADR); rotación automática de responsable por turno (hoy manual, vía
  reasignación); frecuencias quincenal/semestral que los SOP de Limpieza sí
  piden (`remocion-telaranas.md`, `limpieza-horno-piedra.md`) y el dominio
  todavía no cubre; no existe SOP de "cierre de local" propiamente dicho
  (`PROC-OPE-003`) — el módulo automatiza lo que los SOP de apertura y
  limpieza ya describen, no inventa un proceso nuevo.
