# Historial — Módulo `assets`

Estado vigente: 🔶 En curso — slice core (activos, kilometraje/combustible,
mantenimiento, documentos con vencimiento) implementado el 2026-09-09; queda
deuda declarada (`docs/roadmap/deuda/modulo-assets.md`).

## Cronología

### 2026-09-09 — Slice core: activos, mantenimiento, combustible y documentos con vencimiento (ADR-098)

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
