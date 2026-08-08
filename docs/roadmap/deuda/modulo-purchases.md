# Deuda técnica — Módulo purchases (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-07-25 **Migración Alembic** `4ff85f833b29` (proveedor,
  orden_compra, orden_compra_item, recepcion_compra, recepcion_item)
  aplicada a la BD dev (Supabase).
- ✅ 2026-07-25 **Conformidad de comprobante** (`application/comprobantes.py`,
  permiso `purchases.dar_conformidad`): crea el `comprobante` recibido
  (transversal, `shared`), lo liga a la última `recepcion_compra` de la OC
  y publica `purchases.comprobante_conforme` — `accounting` encola el pago
  (ver slice pago a proveedor abajo).
- ⬜ **`cotizacion`**: hoy toda OC tipo `insumo` emite sin cotización
  comparativa (el camino "simplificado" de proveedor preferente es el
  único implementado). Falta el flujo normal (proveedor regular) con
  cotización de respaldo.
- ⬜ **OC tipo `activo` + `requerimiento_activo`**: doble aprobación
  (área + gerencia) y mínimo 2 cotizaciones vinculadas antes de emitir.
  Hoy el tipo está rechazado explícitamente en la capa de aplicación.
- ⬜ **`compra_directa` + caja chica** (`caja_chica_compras`,
  `caja_chica_movimiento`, `rendicion_caja_chica`): compra sin OC a
  proveedor informal, con comprobante obligatorio y rendición semanal
  conciliada por `accounting`.
- ⬜ **`evaluacion_proveedor`** automática (cumplimiento de plazo,
  conformidad, variación de precio) recalculada en cada recepción.
- ⬜ **`orden_compra` no queda marcada como pagada**: `accounting.pago_ejecutado`
  se publica pero `purchases` no lo escucha; `orden_compra.estado` no tiene
  un valor para "pagada" todavía (RN-CMP-014 vive hoy solo del lado de
  `accounting`).
- ⬜ **Listener `inventory.devolucion_a_proveedor`**: gestionar reclamo/
  nota de crédito con el proveedor (bloqueado por `devolucion` en
  inventory, ver arriba).
