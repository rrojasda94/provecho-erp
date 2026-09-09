# ADR-098 — Módulo `assets`: activos, mantenimiento, combustible y documentos con vencimiento

Fecha: 2026-09-09
Estado: aceptada

## Contexto

El grupo tiene equipos (hornos, cámaras de frío) y vehículos de reparto, y
nada del ERP los registra. Tres cosas concretas faltaban, todas pedidas
directamente por el usuario:

1. **Mantenimiento**: un cronograma por equipo/vehículo con aviso antes de
   que venza, no solo la reacción a la avería.
2. **Vehículos**: kilometraje y consumo de combustible por unidad, para
   poder ver si el gasto está fuera de lo normal.
3. **Vencimientos**: SOAT, revisión técnica, licencia de funcionamiento,
   carné de sanidad y similares, con alerta anticipada configurable.

El estado previo del repo era contradictorio con esto:

- `docs/architecture/data-model.md` (§Recursos) y `docs/domain/business-rules.md`
  (RN-VEH-001..004, RN-MNT-001..004, RN-EQP-001..004) **especifican** `activo`,
  `equipamiento`, `vehiculo`, `flota`, `orden_mantenimiento` desde julio de
  2026. Nunca se implementaron.
- **ADR-027 §4 decidió explícitamente no crear `vehiculo`** ("el grupo no
  tiene flota propia") y `docs/roadmap/deuda/modulo-inventory.md` lo dejó
  como "vuelve a la mesa si aparece reparto propio con flota". El usuario
  confirma que sí hay vehículos que registrar: **esa decisión queda
  superada**, no vigente.
- La decisión de 2026-08-05 sobre módulos transversales
  (`docs/roadmap/historial/fundaciones-y-arquitectura.md`) fijó que
  "Activos" **no** seria un módulo aparte para no partir el ciclo de compra:
  se compran en `purchases` (OC tipo `activo`, aún sin implementar — deuda
  declarada) y se deprecian en `accounting` (deuda declarada). Esa decisión
  cubre el **ciclo de compra y depreciación contable**, no el registro
  operativo del día a día (kilometraje, mantenimiento, vencimientos), que
  quedó sin dueño. Este ADR no revierte esa parte: `purchases` sigue
  comprando y `accounting` seguirá depreciando cuando exista ese slice;
  `assets` es el registro operativo que faltaba.
- Permisos y certificados con fecha de vencimiento (SOAT, Defensa Civil,
  fumigación, carné de sanidad, licencia de conducir) no existían como dato
  en ningún lado del ERP — ni una tabla, ni una mención fuera de checklists
  en Markdown.
- El mecanismo de alertas ya es genérico (ADR-033): un evento del bus →
  `Emision` en `src/modules/reports/domain/catalogo.py` → regla de
  distribución → bandeja de `users` → campana. No hacía falta inventar nada
  nuevo para avisar, solo usarlo.

## Decisión

**Un módulo nuevo, `assets`**, dueño de: `activo` (equipamiento o vehículo),
`vehiculo` (extiende `activo` 1:1), `lectura_odometro`, `carga_combustible`,
`plan_mantenimiento`, `orden_mantenimiento` y `documento_vigencia`. Sigue el
mismo contrato de `docs/engineering/module-guide.md` que cualquier módulo
nuevo (los siete registros de activación).

### El combustible entra por Compras, no por un gasto propio de `assets`

Decidido con el usuario (2026-09-09): el comprobante de la carga de
combustible se registra **primero en `purchases`**, con la compra directa
(ADR-082) sobre un artículo `tipo="servicio"` — el mismo mecanismo que ya
existe para "la luz, un flete, un mantenimiento" (`inventory/README.md`).
Desde `assets`, registrar una carga es **ligar** ese comprobante ya recibido
al vehículo, con el kilometraje y los galones.

Por qué no un flujo de gasto propio en `assets`:

- **No hay dos caminos para lo mismo.** Un gasto de combustible es una
  compra a un proveedor (el grifo). `purchases` ya resuelve comprobante,
  proveedor, y de ahí `accounting` arma el asiento por
  `categoria.asiento_contable_config`. Un segundo camino de gasto en
  `assets` duplicaría esa cadena entera para un caso que ya está cubierto.
- **La carga de combustible no es dueña del comprobante fiscal.** `assets`
  necesita el kilometraje y el galonaje —cosas que Compras no tiene por qué
  saber—, pero el papel en sí (RUC del emisor, serie, correlativo,
  unicidad) es dominio de `purchases`/`shared`. Separarlo así respeta
  Clean Architecture: `assets` consume el id del comprobante, nunca su
  ORM.
- `carga_combustible.comprobante_id` es **NOT NULL + UNIQUE**: RN-VEH-006
  exige que cada carga tenga su propio papel, y ninguno se reutilice en dos
  cargas ni en una orden de mantenimiento (mismo comprobante, dos gastos,
  sería duplicar el descargo contable).

### `documento_vigencia` es polimórfico y sin FK

El pedido cubre cuatro sujetos que viven en tres módulos: `activo` (este
módulo), `sucursal`/`empresa` (`users`) y `trabajador` (`rrhh`). Ninguna FK
real cubre los cuatro a la vez. Mismo patrón que `notificacion.referencia_tipo`/
`referencia_id` y `decision_gerencial`: `sujeto_tipo` + `sujeto_id` (UUID sin
FK), validado en `application/scope.exigir_sujeto` según el tipo — `activo`
contra este módulo, `sucursal`/`empresa` contra `users.infrastructure.models`
(permitido por la excepción `*` de `tests/test_arquitectura.py`), y
`trabajador` contra el contrato público nuevo
`rrhh.application.queries_publicas.trabajador_resumen`.

El catálogo de `tipo_documento` es cerrado y vive en
`domain/rules.TIPOS_DOCUMENTO` (mismo criterio que
`reports.domain.catalogo`): una lista abierta por API dejaría entrar
cualquier texto y el filtro por tipo se rompería con el primer error de
tipeo.

**Renovar no edita, crea.** `renovar_documento` deja el documento vencido
como está y encadena uno nuevo vía `renovado_por_id` — una inspección puede
pedir ver el SOAT vencido de hace un año igual que el vigente de hoy, y
sobrescribir la fecha de vencimiento borraría esa evidencia.

### Alertas: cinco emisiones nuevas, ningún mecanismo nuevo

`assets.mantenimiento_proximo`, `assets.mantenimiento_vencido`,
`assets.documento_por_vencer`, `assets.documento_vencido` y
`assets.consumo_anomalo` se agregan al catálogo cerrado de `reports`
(ADR-033). El módulo `reports` ya se suscribe a todo lo que hay en su
`CATALOGO`, así que `assets` no necesita `application/listeners.py` propio.

Los cuatro primeros los publica un barrido diario
(`assets.barrer_vencimientos`, Celery beat 06:30, después de los dos de
`inventory`), **una sola vez por ventana**: `aviso_proximo_en`/
`aviso_vencido_en` en la fila son la marca de que ya se avisó, y se limpian
al realizar la orden de mantenimiento o cuando el estado vuelve a la
normalidad (documento renovado, plan editado). `assets.consumo_anomalo` se
publica en el momento, al registrar la carga.

Se agrega el área **`compras`** a `AREAS_BASE` (no existía): RN-MNT-004
dirige el reporte que adelanta un mantenimiento a compras y a contabilidad,
y hasta ahora no había a quién apuntarle en compras.

### Tenant

`activo` y `documento_vigencia` llevan `empresa_id` propio; el resto del
módulo hereda el alcance de su activo. Un recurso ajeno responde **403**
(`FueraDeAlcance` vía `Tenant.exigir_empresa`), el mismo criterio que
`purchases.application.scope` — no 404: el ERP no usa 404 para "existe pero
no es tuyo" salvo cuando el filtro de tenant ya deja la fila fuera de una
consulta (no cuando se carga por id y se valida después).

### Lo que se deja fuera, a propósito (deuda declarada)

- **`flota`** y **`repuesto_compatibilidad`**: sin reparto con varias
  unidades por categorizar ni control de repuestos por ahora, son
  formularios que hoy nadie llenaría. `docs/roadmap/deuda/modulo-assets.md`.
- **Alta automática del activo al recibir una OC tipo `activo`**: sigue
  bloqueada en `purchases` a la espera de `requerimiento_activo` (deuda ya
  declarada de ese módulo). Cuando exista, publicará un evento que `assets`
  puede consumir para dar de alta el activo solo.
- **Depreciación en `accounting`**: sigue pendiente (deuda ya declarada de
  ese módulo); `assets.valor_compra`/`vida_util_meses` quedan ahí como
  insumo para cuando se construya.
- **`guia_remision.vehiculo_placa`** sigue siendo texto libre: reemplazarla
  por una FK a `vehiculo` es deuda de `inventory`, no de este slice.
- **Adjuntos de `documento_vigencia`** son solo metadata (mismo patrón que
  `marketing.application.adjuntos`): la subida binaria a S3 la hace el
  cliente directo contra el storage, no este módulo.

## Consecuencias

- `src/shared/parametros.MODULOS` gana `"assets"`: el módulo puede tener
  parámetros operativos propios por empresa (ADR-014). El primero es
  `assets/tolerancia_consumo_pct` (default 25 %), que decide cuándo una
  carga de combustible se marca anómala.
- `reports.domain.catalogo.AREAS_BASE` gana el área `compras`; el seeder la
  crea en bases existentes sin migración de datos (`_seed_distribucion` usa
  `_get_or_create` por área y empresa).
- `src/core/destinos.py` gana dos destinos (`activo`, `documento_vigencia`)
  para que la campana lleve del aviso a la pantalla correspondiente.
- Nueve tablas nuevas, una migración (`alembic/versions/30270ac890b1_*`).

## Alternativas descartadas

- **Meter el registro de activos dentro de `purchases`.** Mezclaría el
  ciclo de compra con mantenimiento y flota, que no comparten cohesión ni
  ciclo de vida (un activo vive años después de comprado). `purchases`
  sigue siendo dueño de la compra; `assets`, del activo ya adquirido.
- **Un flujo de gasto de combustible propio en `assets`.** Habría duplicado
  la cadena comprobante → proveedor → asiento que `purchases`/`accounting`
  ya resuelven, por un tipo de gasto que no es distinto a cualquier otro.
- **`documento_vigencia` con cuatro FK nullable (una por sujeto).** Más
  explícito en el esquema, pero exige NULL-check en cada consulta y un
  `CHECK` que garantice que exactamente una está llena; el par
  `sujeto_tipo`/`sujeto_id` es el mismo patrón que ya usa `notificacion`.

## Referencias

- ADR-004 (tenant desde el JWT), ADR-014 (parámetros operativos), ADR-016
  (eventos post-commit), ADR-027 (guía de remisión — su §4 queda superado
  por este ADR), ADR-033 (emisión y distribución de reportes), ADR-036
  (destinos de un reporte), ADR-082 (compra directa).
- `docs/roadmap/deuda/modulo-assets.md`,
  `docs/roadmap/historial/modulo-assets.md`.
- Reglas: `RN-VEH-001..007`, `RN-MNT-001..005`, `RN-EQP-001..004`,
  `RN-DOC-001..004` en `docs/domain/business-rules.md`.
- `src/modules/assets/README.md`, `docs/architecture/events.md`.
