- **La reposición por venta anulada vuelve al lote del que salió, no al
  lote del día** (ADR-094). `movimiento_inventario.referencia` ya guardaba
  el `venta_id` en cada salida —incluida la que reparte por FEFO entre
  varios lotes— así que no hizo falta cambiar el contrato del evento: se
  reconstruye de cuáles lotes salió y se repone en ese mismo orden (por
  vencimiento, no por `ts`, que puede empatar dentro de la misma
  transacción). Una reposición parcial —nota de crédito por menos de lo
  vendido— prioriza el lote que salió primero, sin pasarse de lo que
  entregó. Sin rastro —venta anterior a este cambio— cae al comportamiento
  de siempre. Alcanza a `sales.venta_anulada`, `lineas_anuladas` y
  `nota_credito_emitida`, que comparten el mismo listener.
