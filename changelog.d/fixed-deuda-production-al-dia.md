- **La deuda de `production` decía estar bloqueada por `inventory`, y ya no lo
  estaba** (2026-09-09). `docs/roadmap/deuda/modulo-production.md` marcaba la merma
  del desecho, el lote/FEFO del producto terminado y el conteo cíclico del almacén
  de producción como "bloqueados por deuda de inventory". Los tres bloqueos se
  saldaron en `inventory` entre el 2026-07-27 y el 2026-08-06 (ADR-015, ADR-028, el
  conteo siempre fue genérico por `almacen_id`) y nadie actualizó el doc de
  `production`: quien lo leyera creía que el trabajo estaba del otro lado. Se
  reescribe con la causa real (los tres son trabajo pendiente **dentro** de
  `production`, no de `inventory`) y se agregan ocho ítems de deuda que existían en
  el código pero no en ningún doc: costeo tipeado en vez de calculado desde
  `articulo.costo_promedio`, cero auditoría, idempotencia solo en crear la orden,
  tarifa de mano de obra global en `.env` en vez de `parametro_empresa`, el módulo
  sin escuchar `inventory.stock_bajo_minimo` pese a que su propio README lo
  prometía, RN-CDP-001 (nunca despacha a sucursal) sin ningún control en código,
  doble mecanismo de evidencia para RN-PRD-015, y un seeder sin usuario/almacén/receta
  de producción que hace el módulo imposible de probar sin `admin`. Se cierra por
  decisión escrita la segregación crear/completar (no se exige, se compensa con
  auditoría). Nuevo `docs/roadmap/deuda-production-2026-09-09.md` con el plan
  completo para saldar todo esto en bloques, en el mismo formato que la auditoría
  del 2026-08-30. De paso, `docs/roadmap/deuda/modulo-accounting.md` también mentía:
  listaba `sales.comprobante_emitido`, `inventory.transferencia_recibida` e
  `inventory.merma_registrada` como eventos sin publicar cuando los tres se asientan
  desde 2026-08-06/2026-08-31, y `docs/architecture/events.md` documentaba un
  payload de `production.orden_completada` que el código nunca usó (tres de cinco
  nombres mal) y no tenía fila para `production.consumo_registrado`, publicado desde
  el primer día del slice.
  Costo aceptado: este PR es solo documentación y planificación — el código de
  `production` no cambia todavía. Los bloques del plan se ejecutan en sesiones
  separadas.
