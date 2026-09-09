- **Repuestos compatibles y consumo en la orden de mantenimiento** (2026-09-09,
  `assets`). RN-RPT-002 estaba especificada desde siempre sin código:
  `repuesto_compatibilidad` liga un artículo de `inventory` a un activo como
  sugerencia (no bloquea registrar uno no listado), y `realizar` una orden de
  mantenimiento acepta ahora una lista de repuestos usados — se congela el
  nombre del artículo en la línea y se publica `assets.repuesto_consumido`
  para que `inventory` descuente stock, con el mismo criterio no bloqueante
  que el consumo de producción (RN-MNT-006): sin SKU activo o sin stock
  suficiente queda una `incidencia_inventario`, la orden no se frena.
