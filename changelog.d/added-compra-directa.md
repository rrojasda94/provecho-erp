- **Compra directa** (`POST /purchases/compras-directas`, ADR-082): sustenta
  un gasto ya incurrido — factura de un proveedor informal, sin orden de
  compra previa — en una sola llamada. Reutiliza `orden_compra` con
  `origen="directa"` (la crea, la emite, la recibe al 100% y da conformidad
  del comprobante de una vez) en vez de un modelo aparte, así que `inventory`
  (entra stock) y `accounting` (asienta y paga) no necesitaron ningún cambio:
  reciben el mismo evento `purchases.compra_recibida` de siempre. No pasa por
  el umbral de aprobación (es gasto ya incurrido) ni por caja chica —ese
  modelo sigue sin existir, el pago sale por cuentas por pagar normal.
