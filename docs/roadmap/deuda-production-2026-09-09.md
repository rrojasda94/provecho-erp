# Plan de deuda — Módulo `production` (2026-09-09)

Mismo formato que [`auditoria-erp-2026-08-30.md`](auditoria-erp-2026-08-30.md): cada
bloque = una rama + una sesión de Claude Code + un PR en borrador desde el primer
commit, que se abre contra `main` solo cuando el bloque completo está verde (los 6
jobs del CI, rama al día con `main`). Los bloques de un mismo carril no comparten
archivos entre sí y se pueden trabajar en paralelo; los del carril A sí comparten
`src/modules/production/application/ordenes.py` y van en serie.

## Por qué

`production` tiene su slice core (crear → consumo → completar, costeo automático)
desde 2026-07-25 y casi no se tocó desde entonces. Al revisarlo para esta sesión
aparecieron tres problemas, no solo una lista de pendientes:

1. **La deuda documentada mentía.** `docs/roadmap/deuda/modulo-production.md` decía
   que la merma, el lote/FEFO y el conteo cíclico estaban "bloqueados por deuda de
   inventory". Los tres bloqueos ya no existen: la merma vive en `reserva_stock`
   desde ADR-028 (sin tabla `stock_merma`, que fue decisión, no diferimiento), el
   lote con `origen=produccion` se crea desde ADR-015, y el conteo cíclico es
   genérico por `almacen_id` — ya funciona sobre un almacén tipo `produccion` sin
   tocar una línea de `inventory`. Lo que falta en los tres casos es trabajo dentro
   de `production`, no de `inventory`.
2. **Las integraciones están a medias.** El costeo "automático" (RN-PRD-018) recibe
   el `costo_unitario` que tipea el cliente en vez de leer `articulo.costo_promedio`;
   el desperdicio real nunca se contrasta contra `receta_item.merma_pct`; el desecho
   guarda `merma_cantidad`/`merma_motivo` pero nunca dispara un asiento contable; el
   lote producido nace sin `fecha_vencimiento`; el módulo no tiene ni una llamada a
   `auditoria.registrar`; la idempotencia solo cubre crear la orden; la tarifa de
   mano de obra es un valor global en `.env` en vez de `parametro_empresa`;
   `production` no escucha `inventory.stock_bajo_minimo` pese a que su propio README
   dice que sí; RN-CDP-001 (una cocina de producción nunca despacha a sucursal) no
   tiene ningún control en código; hay dos mecanismos de evidencia distintos para la
   misma regla (RN-PRD-015).
3. **No se puede probar sin el usuario `admin`.** El seeder no crea un usuario con
   rol `jefe_cocina`, ni un almacén tipo `produccion`, ni una receta con
   `articulo_id` — sin esa receta, crear una orden se rechaza (409). La pantalla
   `/produccion` existe (listado + 3 diálogos) pero no gatea botones por permiso, no
   pasa `usuario.permisos` al cliente, no tiene ficha de detalle pese a que el
   endpoint `GET /ordenes/{id}` existe, y pagina en el cliente.

A esto se suman las tres entidades que el spec de `data-model.md` §7 documenta y el
código nunca implementó: `plan_produccion`, `checklist_inocuidad_turno`,
`reporte_produccion`.

## Decisiones tomadas (2026-09-09)

- **Alcance**: deuda declarada + integraciones + las tres tablas del spec (no se
  posterga nada a 2027 salvo lo que ya estaba fuera de alcance: la cocina física).
- **Contabilidad de producción**: se mantiene el circuito de mercaderías que
  `accounting/domain/plantillas.py` ya eligió a propósito (601→201→611, no el de
  producción 602→241→21→702, porque el ERP no lleva costos por orden en el sentido
  contable). Se agrega **un solo asiento nuevo**: el desecho de una orden
  (`no_conforme_desechado`) asienta `6599 (merma) / 201 (existencia)` por el costo de
  insumos de la orden — la mano de obra ya es gasto (62) y el producto terminado
  nunca entró a inventario, así que no hay reserva que desechar. Documentado en un
  ADR nuevo.
- **Segregación crear/completar**: no se exige usuario distinto (a diferencia de
  `inventory.ajuste`). Se cierra por decisión escrita en la deuda del módulo, con
  auditoría dejando registrado quién hizo cada paso.
- **Horas-hombre**: se derivan de la asistencia real de RRHH (`asistencia`/
  `marcacion`) vía un contrato público nuevo, en vez de seguir tipeándose.

## Carriles

- **Carril A** (`src/modules/production/application/ordenes.py`, en serie): B2, B5,
  B6, B7, B8, B9, B10, B11, B12, B13.
- **Carril B** (otros módulos, en paralelo desde el día 1): B1, B3, B4.
- **Carril C** (frontend, depende de A): B6f.
- **Cierre**: B14, recuento final.

## Tabla de bloques

| Rama | Hallazgos | Archivos | Sev. | Esfuerzo |
|---|---|---|---|---|
| `feat/produccion-semilla-y-pantalla-con-permisos` (B1) | Sin usuario `jefecocina1`, sin almacén `produccion`, sin receta con `articulo_id` en ningún seeder — el módulo no se puede ejercitar sin `admin`. Pantalla sin gates por permiso ni `usuario.permisos`, paginación client-side. | `src/seeders/{seed,e2e}.py`, `frontend/app/(app)/produccion/{page,ordenes-cliente}.tsx`, `CLAUDE.md` | 🔴 | S |
| `feat/produccion-costeo-real` (B2) | `costo_unitario` tipeado en vez de `articulo.costo_promedio`; sin consumo sugerido desde la receta BOM; desperdicio real nunca contrastado contra `receta_item.merma_pct`; tarifa de mano de obra global en `.env`. | `production/{api,application,domain,infrastructure}`, migración, `events.md` | 🟠 | L |
| `fix/inventario-cdp-001-y-conteo-produccion` (B3) | RN-CDP-001 (nunca despacha a sucursal) sin control en `transferencias._validar_almacenes`; conteo cíclico sin cobertura de test sobre almacén `produccion`. | `inventory/application/transferencias.py`, `tests/test_transferencias.py`, `tests/test_conteos.py` | 🟠 | S |
| `feat/rrhh-horas-asistidas-contrato-publico` (B4) | `rrhh.queries_publicas` solo expone nombres; falta un contrato de horas asistidas para que production deje de tipear `horas_hombre`. | `rrhh/application/queries_publicas.py` | 🟡 | S |
| `feat/produccion-lote-trazabilidad-auditoria` (B5) | El lote producido nace sin `fecha_vencimiento`/`lote_codigo` (el listener de inventory ya los sabe leer); cero `auditoria.registrar` en todo el módulo; idempotencia solo en crear, no en consumo/completar. | `production/**`, migración | 🟠 | M |
| `feat/produccion-desecho-a-contabilidad` (B6) | El desecho nunca dispara un asiento contable pese a declarar `merma_cantidad`/`merma_motivo`. | `production/application/ordenes.py`, `accounting/{domain/plantillas.py,application/listeners.py}`, ADR nuevo | 🔴 | M |
| `feat/produccion-evidencia-como-archivo` (B7) | Dos mecanismos de evidencia para RN-PRD-015: `evidencia_destruccion_url` (string) en production vs. `evidencia_id` (FK `archivo`) en reports. | `shared/adjuntos.py` (extraído de marketing), `production`, `reports` catálogo, migración | 🟠 | M |
| `feat/produccion-horas-hombre-desde-rrhh` (B8) | Depende de B4. `horas_hombre` sigue tipeado en vez de tomarse de la asistencia real. | `production`, migración, frontend | 🟡 | M |
| `feat/produccion-orden-por-necesidad` (B9) | `production` no escucha `inventory.stock_bajo_minimo` pese a que el README lo promete (RN-PRD-007/011). | `production/application/listeners.py` (nuevo), `core/app.py`, migración | 🟡 | M |
| `feat/produccion-plan-de-produccion` (B10) | `plan_produccion` del spec §7 no existe: toda orden es ad-hoc, sin cronograma (RN-PRD-011/012). | `production`, `inventory` (solo `reservas` público), seeder, migración, frontend | 🟠 | L |
| `feat/produccion-checklist-inocuidad` (B11) | `checklist_inocuidad_turno` no existe: nada bloquea la cocina por falla de inocuidad o frío (RN-CDP-005). | `production`, `reports` catálogo, migración, frontend | 🟠 | L |
| `feat/produccion-reporte-de-jornada` (B12) | `reporte_produccion` no existe: RN-DOC-010 (reporte automático al cierre, visado no redactado) sin implementar. | `production`, `celery_beat`, `reports` catálogo, migración, frontend | 🟡 | M |
| `feat/produccion-subrecetas-anidadas` (B13) | Una orden que consume otra subreceta (con su propia orden) no está resuelta. | `production`, migración, frontend | 🟡 | M |
| `feat/produccion-ficha-y-consumo-sugerido` (B6f) | Sin ficha `[id]` pese a que `GET /ordenes/{id}` existe; sin submenú más allá de "Órdenes". Depende de B2 y B5. | `frontend/app/(app)/produccion/**` | 🟠 | M |
| `docs/deuda-production-recuento-final` (B14) | Cierre: recontar `ROADMAP.md`, actualizar historial y `data-model.md` §7 contra el código final. | `ROADMAP.md`, `docs/roadmap/historial/modulo-production.md`, README del módulo, `data-model.md` | — | S |

## Orden sugerido

```
Semana 1: P0 (este documento + docs al día) → en paralelo B1, B2, B3, B4
Semana 2: B5 → B6 (carril A)  |  B6f (carril C, tras B2/B5)
Semana 3: B7 → B8 (carril A)  |  B9 puede ir en paralelo si no toca `completar`
Semana 4+: B10 → B11 → B12 → B13 → B14
```

## Reutilizar (no reinventar)

- Costeo teórico y conversión de unidades de medida:
  `inventory/application/recetas.py` (`costo_linea`, `detalle_receta`),
  `inventory/domain/rules.py` (`consumo_de_linea`, `convertir_cantidad`).
- Parámetro por empresa con semilla en `.env`: patrón de
  `sales/application/tarifa_delivery.py`.
- Auditoría: `src/shared/auditoria.py:registrar`. Idempotencia: columna única +
  lookup previo, como ya hace `production/infrastructure/repositories.py`.
- Plantilla contable + listener: `accounting/domain/plantillas.py`,
  `accounting/application/listeners.py:on_merma_registrada` es el molde exacto
  para el asiento de desecho.
- Catálogo de reports para eventos nuevos: `reports/domain/catalogo.py`.
- Adjuntos/S3: `marketing/application/adjuntos.py` (a extraer a `shared`).
- Pantallas: `frontend/app/(app)/compras/ordenes-compra/**` (listado + ficha +
  gates de permiso), `inventario/transferencias/**` (listado con acciones).

## Cómo usar esto en sesiones separadas

Al abrir una sesión nueva para un bloque, pasarle: *"trabaja el bloque
`<nombre-de-rama>` del plan `docs/roadmap/deuda-production-2026-09-09.md`"*. Cada
sesión crea la rama, hace commits incrementales, corre `ruff`/`eslint`/pruebas, y
abre el PR en borrador contra `main` solo cuando el bloque completo esté en verde
(los 6 jobs del CI, rama al día con `main`). Ver
[`docs/engineering/trabajo-en-paralelo.md`](../engineering/trabajo-en-paralelo.md)
para coordinación entre ramas simultáneas (ADR, migración, changelog, deuda técnica).

## Verificación

Por bloque, antes de abrir o actualizar el PR:

```bash
ruff check . && pytest
python -m src.core.openapi_export && git diff --exit-code docs/architecture/openapi.json
alembic heads   # una sola cabeza
cd frontend && npm run lint && npm run typecheck && npm test && npm run build && npm run test:e2e
```

Extremo a extremo del módulo (desde B1 en adelante): login `jefecocina1`/`123456` →
`/produccion` → nueva orden de la subreceta semilla en el almacén de producción →
consumo sugerido → completar `conforme` con `fecha_vencimiento` → verificar en
`/inventario` que entró el stock, el lote con vencimiento y se recalculó
`costo_promedio`; completar otra orden como `no_conforme_desechado` con evidencia →
verificar el asiento 6599/201 en `/contabilidad/libro-mayor` y el escalamiento en
`/reportes`.
