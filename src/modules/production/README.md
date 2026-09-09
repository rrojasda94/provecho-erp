# Módulo `production` — Producción de subrecetas

**Estado (2026-07-25):** slice core implementado (código, sin operación
real — primera cocina de producción planeada para 2027,
`docs/produccion/README.md`). Se construyó antes de esa fecha por pedido
explícito, siguiendo el mismo patrón slice-por-slice que
purchases/inventory/sales.

## Objetivo

Planificar y ejecutar la elaboración de subrecetas en cocina de
producción según cronograma + necesidad de Almacén Central, con control
de calidad obligatorio y trazabilidad completa por lote.

## Entidades

`plan_produccion` (cronograma: fecha, turno, línea de producción/tipo de
receta, origen `cronograma_fijo`|`ajuste_por_necesidad`), `orden_produccion`
(articulo_id subreceta, cantidad, almacen_id, plan_produccion_id opcional,
control_calidad_resultado, desperdicio/merma, costeo automático:
horas_hombre, costo_insumos, costo_mano_obra, costo_real_unitario —
RN-PRD-018), `consumo_produccion_item` (detalle de insumos consumidos por
orden: cantidad, costo_unitario, peso_desperdicio_real, tipo_desperdicio —
contrastado contra `receta_item.merma_pct`), `checklist_inocuidad_turno`
(bioseguridad, superficies, limpieza intermedia, equipos_frio JSONB,
plaga_indicio — bloquea la cocina si algo falla, RN-CDP-005),
`reporte_produccion` (jornada, visado_por, consolidado automático al
cierre). Detalle en `docs/architecture/data-model.md` §7.

`reporte_escalamiento` (origen `produccion`) vive en `reports` desde
ADR-036 — no en `shared`, como decía `data-model.md` §6 antes de que el
módulo existiera — y `lote` está modelada por `inventory`; `production`
las reutiliza, no las duplica. La no conformidad se escala **desde el
reporte** que emite `production.no_conformidad_detectada`, no desde la orden.

## Estado (slice core implementado 2026-07-25)

Operativo en `/api/v1/production`: `orden_produccion` ad-hoc (sin
`plan_produccion`/cronograma — diferido) crear (borrador) → registrar
consumo real de insumos (`consumo_produccion_item`, transición a
`en_proceso`) → completar con resultado de control de calidad
(`conforme` | `no_conforme_reprocesado` | `no_conforme_desechado`).
Costeo automático al completar (RN-PRD-018): `costo_insumos` (suma de
consumo real), `costo_mano_obra` (`horas_hombre` × tarifa única
configurable `production_costo_hora_mano_obra`), `costo_real_unitario`.
Resuelve la receta de la subreceta vía el nuevo `receta.articulo_id`
(nullable — liga una receta a la subreceta que produce, distinto del uso
existente `producto_comercial.receta_id` de venta directa). Capas
`domain/rules.py`, `infrastructure/repositories.py`, `application/`
(`ordenes.py`), `api/`. Migración `f78501175fba` aplicada.

| Método | Ruta | Permiso |
|--------|------|---------|
| POST | `/ordenes` | `production.crear` |
| GET | `/ordenes/{id}` | `production.leer` |
| POST | `/ordenes/{id}/consumo` | `production.crear` |
| POST | `/ordenes/{id}/completar` | `production.completar` |

Eventos: publica `production.consumo_registrado` (inventory descuenta
insumos, tipo `consumo_produccion`), `production.orden_completada`
(inventory suma stock del artículo terminado, tipo `produccion_entrada`,
y recalcula su `costo_promedio` — mismo listener/patrón que
`purchases.compra_recibida`) y `production.no_conformidad_detectada`
(sin consumidor todavía). Rol semilla `jefe_cocina`.

Deuda del slice (ver
[plan de deuda](../../../docs/roadmap/deuda-production-2026-09-09.md) y
[`docs/roadmap/deuda/modulo-production.md`](../../../docs/roadmap/deuda/modulo-production.md)):
`plan_produccion`/cronograma (hoy la orden se crea sin plan),
`checklist_inocuidad_turno` (bloqueo de cocina por fallo de inocuidad),
`reporte_produccion` consolidado, asiento contable propio para el desecho
(la merma de `inventory` no aplica: el producto terminado de una orden
desechada nunca entró a inventario), lote/trazabilidad del producto
terminado (el listener de `inventory` ya sabe leer `fecha_vencimiento`;
falta que `production` la mande), subrecetas anidadas (una orden que
consume otra subreceta con su propia orden), costeo real (hoy
`costo_unitario` lo tipea el cliente), auditoría e idempotencia
incompletas.

## Casos de uso

- Definir plan de producción del periodo (cronograma fijo por tipo de
  receta/proceso, evita contaminación cruzada).
- Generar orden de producción, desde el plan o por ajuste ante alerta de
  stock mínimo de `inventory` (RN-PRD-007/011).
- Ejecutar orden: consumir insumos/subrecetas, producir lote(s) con
  código y trazabilidad completa (manipulador, envasador, variables de
  proceso).
- Control de calidad de la orden antes de habilitar despacho: conforme,
  no conforme reprocesado, o no conforme desechado.
- No conformidad (cualquier resultado no conforme) emite el reporte, y desde
  ahí se abre el `reporte_escalamiento` (origen `produccion`, ADR-036);
  desecho exige evidencia de destrucción adjunta (RN-PRD-015).
- Calcular costo real de la orden automáticamente (insumos consumidos +
  mano de obra) — nunca a mano; el desperdicio real por insumo se
  registra por tipo y peso, contrastado contra el esperado de la receta
  (RN-PRD-018).
- Verificar checklist de inocuidad al inicio de turno, incluyendo
  temperatura de cada equipo de frío; bloquear la cocina y alertar a
  Gerencia si algo falla (RN-CDP-002/005).
- Consolidar reporte de producción al cierre de jornada (RN-DOC-010).
- Conteo cíclico del almacén propio (tipo `produccion`), mismo esquema
  que `inventory` en Almacén Central — el reporte se genera
  automáticamente a partir de los conteos físicos registrados; el jefe de
  cocina visa, no lo redacta a mano.
- Evaluar viabilidad técnica de nuevo producto o mejora de receta a
  pedido de `sales`/Comercial (RN-PRD-017) — completa la ficha, no la
  origina.

## Reglas

- Toda orden de producción pasa control de calidad antes de despachar
  (RN-PRD-013); nunca se salta este paso por presión de cronograma.
- No conformidad siempre genera reporte de escalamiento, se corrija o se
  deseche (RN-PRD-014); desecho sin evidencia de destrucción no cierra
  el reporte (RN-PRD-015).
- Cambio de receta/subreceta notifica con urgencia a quienes fabrican y
  actualiza costos el mismo día (RN-PRD-009).
- Nunca despacha directo a sucursal, solo a Almacén Central (RN-CDP-001).
- Ningún documento de conteo o reporte de producción se llena a mano: se
  genera desde los datos ya registrados en el ERP (peso de balanza,
  lectura QR, horas-hombre); el rol humano es visar, no transcribir.
- Equipo de frío fuera de rango bloquea la cocina y alerta a Gerencia de
  inmediato (RN-CDP-005), igual criterio que la falla de frío en
  apertura de sucursal (RN-SUC-009).

## Flujo

Plan de producción (o necesidad urgente) → orden de producción → consumo
de insumos → elaboración → control de calidad → (conforme: empacado →
almacén de producción → despacho a Almacén Central) | (no conforme:
reproceso o desecho con evidencia → reporte de escalamiento).

## Relaciones

- Escucha: nada todavía. **`inventory.stock_bajo_minimo` está pendiente**
  (RN-PRD-007) — el evento se publica desde 2026-08-06 pero `production`
  no tiene `listeners.py` ni lo consume (deuda técnica, ver ROADMAP).
- Publica: `production.consumo_registrado` (consumido por `inventory` para
  descontar insumos vía FEFO), `production.orden_completada` (consumido
  por `inventory` para sumar producto terminado y recalcular
  `costo_promedio`), `production.no_conformidad_detectada` (consumido por
  `reports`, que abre el `reporte_escalamiento`; consumido por
  Comercial/Gerencia ante reincidencia). El desecho (`merma_cantidad`/
  `merma_motivo` en la orden) todavía **no** dispara ningún asiento
  contable — es deuda pendiente, no se reusa `inventory.merma_registrada`
  porque el producto terminado de una orden desechada nunca ingresó a
  inventory (ver ROADMAP). Reproceso (`no_conforme_reprocesado`)
  correctamente no genera merma ni asiento, solo el detalle de la
  corrección en el reporte de escalamiento.
  `production.equipo_frio_fuera_rango` (alerta inmediata a Gerencia,
  RN-CDP-005) está documentado en `events.md` pero aún no se publica
  (depende de `checklist_inocuidad_turno`, deuda técnica).
