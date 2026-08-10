# Deuda técnica — Módulo production (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-07-25 **Migración Alembic** `f78501175fba` (orden_produccion,
  consumo_produccion_item, receta.articulo_id) aplicada a la BD dev
  (Supabase).
- ⬜ **`plan_produccion`** (cronograma fijo por tipo de receta/turno,
  evita contaminación cruzada): hoy toda orden se crea ad-hoc, sin plan.
- ⬜ **`checklist_inocuidad_turno`**: bioseguridad, superficies, equipos
  de frío (JSONB), indicio de plaga — bloquea la cocina si algo falla
  (RN-CDP-005), igual criterio que falla de frío en apertura de sucursal.
- ⬜ **`reporte_produccion`** consolidado automático al cierre de jornada
  (RN-DOC-010), visado por el jefe de cocina, no redactado a mano.
- ✅ **`reporte_escalamiento` real** (2026-08-09, ADR-036): la entidad existe,
  vive en `reports` (no en `shared`, ver el ADR) y la cadena se abre **desde el
  reporte** que emite `production.no_conformidad_detectada`. `registrado_por`
  se agregó al payload para que el reporte diga quién cerró la orden.
- ⬜ **Merma → `accounting`**: `no_conforme_desechado` registra
  `merma_cantidad`/`merma_motivo` en la orden pero no dispara
  `inventory.merma_registrada` (bloqueado por `stock_merma`, deuda de
  inventory) — sin ese evento, el asiento contable de la merma no llega.
  Mismo bloqueo para el costeo por lote (ver siguiente punto).
  Reproceso (`no_conforme_reprocesado`) correctamente no genera merma ni
  asiento (RN-PRD — solo detalle en el reporte de escalamiento).
- 🔶 **Lote/trazabilidad del producto terminado**: desde 2026-07-27
  (ADR-015) el ingreso por `orden_completada` **sí** genera `lote`
  (`origen=produccion`, referencia a la orden) cuando el artículo controla
  lote. Falta la trazabilidad fina de fabricación —manipulador, envasador,
  línea, variables de proceso, QR (RN-PRD, RN-LOT-002/003)—: son campos
  del slice de `production`, que además debe mandar la fecha de
  vencimiento (hoy el lote producido nace sin ella, RN-VNC-001).
- ⬜ **Subrecetas anidadas**: una orden que consume otra subreceta (con su
  propia orden de producción) no está resuelta — hoy `registrar_consumo`
  espera insumos ya disponibles en stock.
- ⬜ **Conteo cíclico del almacén de producción**: mismo esquema que
  `inventory` en Almacén Central (bloqueado por conteo, deuda de
  inventory).
- ⬜ **Segregación quien crea vs. quien completa la orden**: hoy
  `production.crear`/`production.completar` son permisos distintos pero
  nada impide que el mismo usuario tenga ambos y haga las dos acciones
  (a diferencia de `inventory.ajuste`, que sí exige aprobador≠solicitante) —
  evaluar si el negocio lo requiere para producción.
