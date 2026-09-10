### Added

- `purchases`: nueva orden de compra tipo `activo` (`crear_orden_compra_activo`)
  con `requerimiento_activo` (sin ítems de `inventory`, recepción total vía
  `recibir_orden_compra_activo`).
- `assets`: primer listener del módulo — consume
  `purchases.requerimiento_activo_recibido` y da de alta el activo
  (`tipo="equipamiento"`) automáticamente al recibir la OC.
