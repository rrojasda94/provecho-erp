# Historial — Módulo `assets`

Estado vigente: 🔶 En curso — slice core (activos, kilometraje/combustible,
mantenimiento, documentos con vencimiento) implementado el 2026-09-09, y el
mismo día se cerró toda la deuda declarada al cerrarlo salvo `flota`
(repuestos, alta automática desde `purchases`, depreciación en
`accounting`, `guia_remision.vehiculo_id`, adjuntos a S3, canal de alerta
por email); ver `docs/roadmap/deuda/modulo-assets.md`.

## Cronología

### 2026-09-09 — Slice core: activos, mantenimiento, combustible y documentos con vencimiento (ADR-099)

El usuario pidió directamente lo que faltaba: mantenimiento y cronograma de
equipos y vehículos, kilometraje, comprobantes de combustible por vehículo
para poder ver si el consumo va bien, y permisos/certificados con
vencimiento y alerta anticipada. Nada de esto tenía código — solo
especificación en `data-model.md`/`business-rules.md` desde julio de 2026,
y una decisión explícita de **no** crear `vehiculo` (ADR-027 §4, "el grupo
no tiene flota"). El usuario confirmó que sí hay vehículos: esa decisión
queda superada.

Se creó el módulo `assets` con `activo` (equipamiento o vehículo),
`vehiculo` (extiende `activo` 1:1), `lectura_odometro` (odómetro monótono,
RN-VEH-005), `carga_combustible` (liga un comprobante ya **recibido** en
`purchases` — decisión con el usuario: el combustible se compra como
cualquier otro servicio vía compra directa, ADR-082, y `assets` solo
consume el id del comprobante; calcula rendimiento km/galón y marca
`anomalo` cuando cae muy por debajo del promedio reciente, RN-VEH-006/007),
`plan_mantenimiento` + `orden_mantenimiento` (aviso con anticipación
configurable por días y/o kilometraje, RN-MNT-001..005) y
`documento_vigencia` (polimórfico entre activo/sucursal/empresa/trabajador,
catálogo cerrado de tipos — SOAT, revisión técnica, licencia de
funcionamiento, Defensa Civil, fumigación, registro sanitario, carné de
sanidad, licencia de conducir — RN-DOC-001..004).

Las alertas no inventaron mecanismo: se agregaron cinco emisiones al
catálogo cerrado de `reports` (ADR-033) —
`assets.mantenimiento_proximo`/`vencido`,
`assets.documento_por_vencer`/`vencido`, `assets.consumo_anomalo`— y
`reports` ya se suscribe a todo su `CATALOGO`, así que `assets` no necesita
listener propio. Los cuatro primeros los publica un barrido diario
(`assets.barrer_vencimientos`, Celery beat 06:30), idempotente por ventana
(`aviso_proximo_en`/`aviso_vencido_en`, mismo criterio que
`sales.alerta_pedido`). Se agregó el área `compras` a `AREAS_BASE` —RN-MNT-004
dirige el reporte de un adelanto de mantenimiento a compras y contabilidad,
y no había a quién apuntarle en compras.

Deliberadamente fuera de este slice: `flota` (agrupador de vehículos,
diferido — sin varias unidades por categorizar es un formulario sin uso),
`repuesto_compatibilidad` (sin control de repuestos todavía), el alta
automática del activo al recibir una OC tipo `activo` (depende de
`requerimiento_activo`, deuda de `purchases`) y la depreciación en
`accounting` (deuda ya declarada de ese módulo) — `assets.activo` queda
listo con `valor_compra`/`vida_util_meses` para cuando ese slice exista, sin
partir el ciclo en un tercer módulo (la decisión de 2026-08-05 sobre
módulos transversales sigue vigente en esa parte).

Migración `30270ac890b1` (nueve tablas). 19 tests en `tests/test_assets.py`
(dominio puro + API con tenant + integración con `reports`, verificando que
el barrido publica una sola vez por ventana). Suite completa verde contra
SQLite y Postgres.

### 2026-09-09 — Cierre de la deuda declarada al abrir el módulo

El mismo día del slice core, con el usuario pidiendo explícitamente "todo,
incluyendo construir lo que falta en purchases/accounting/reports": seis
slices más, cada uno con su propia migración, pruebas y documentación.

- **Repuestos**: `repuesto_compatibilidad` (activo↔artículo `tipo=
  "repuesto"`) y `orden_mantenimiento_repuesto` (líneas de consumo al
  realizar la orden, evento `inventory.movimiento_registrado` con origen
  `orden_mantenimiento`). No bloquea registrar un repuesto no listado.
- **`guia_remision.vehiculo_id`**: FK opcional a `assets.vehiculo` —
  `inventory` resuelve la placa a mostrar por el vehículo si se registró
  uno, o cae al texto libre existente si no. ADR-027 §4 queda superado.
- **Adjuntos con subida real a S3**: `src/shared/integrations/storage/
  s3.py`, mismo patrón de import perezoso que `src/backups/backup.py`
  (ADR-007) — URLs prefirmadas de subida y descarga, sin que `boto3` sea
  obligatorio para correr la API.
- **Canal de alerta por email**: `reports` sumó `canal`
  (`campana`/`email`) a `regla_distribucion`/`entrega_reporte` y
  `src/shared/integrations/email/smtp.py` — deuda de `reports` (ADR-033),
  `assets` la hereda sin cambios propios.
- **Depreciación en `accounting`**: `activo_depreciacion` (línea mensual
  por activo) + barrido `accounting.correr_depreciacion_mensual`
  (PROC-CTB-010), asiento vía `crear_asiento_automatico` existente
  (idempotente por `activo_id:YYYY-MM`, respeta periodo cerrado). Consume
  `assets.application.queries_publicas.activos_depreciables` — el contrato
  público que evita que `accounting` importe el dominio de `assets`.
- **OC tipo `activo` + alta automática**: `purchases` construyó
  `requerimiento_activo` y `crear_orden_compra_activo`/
  `recibir_orden_compra_activo` (sin ítems de `inventory`, recepción
  total). `assets.application.listeners` (primer listener del módulo)
  consume `purchases.requerimiento_activo_recibido` y da de alta el
  activo. La doble aprobación de área/gerencia y las cotizaciones mínimas
  que `purchases` tenía especificadas siguen sin construirse (deuda de ese
  módulo).
- **`tolerancia_consumo_pct`**: el parámetro nunca llegaba a proponerse
  (faltaba en `src/seeders/parametros.py`) y `assets` no estaba en el
  selector de `/gerencia/parametros`. Se corrigieron ambos gaps, y de paso
  un bug en `combustible.tolerancia_consumo` que leía `int(valor)` sobre
  un dict en vez de `valor["porcentaje"]` (nunca se había ejercitado con
  un valor distinto al semilla).

Fusión con `main` el mismo día: `delivery` (reparto propio) se mergeó en
paralelo y también pidió `ADR-098` — se renumeró el de este módulo a
`ADR-099` (`docs/engineering/trabajo-en-paralelo.md`: quien mergea después
renumera). Dos cabezas de Alembic (`e0ef2e91cadc` de este módulo y
`69f4ca1d58f4` de `delivery`) resueltas re-encadenando el `down_revision`
de la primera migración de este módulo a la nueva cabeza, sin migración de
merge — mismo criterio que documenta esa guía.

Queda abierto solo `flota` — ver `docs/roadmap/deuda/modulo-assets.md`.
