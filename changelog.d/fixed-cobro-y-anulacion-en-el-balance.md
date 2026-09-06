- **El balance mostraba ingresos y ninguna plata** (2026-09-05).
  `sales.venta_pagada` se publicaba desde siempre y **no lo escuchaba nadie**:
  la cuenta por cobrar de cada venta quedaba abierta para siempre y el
  efectivo cobrado no entraba a ninguna cuenta. Ahora el cobro cancela la
  `1212` y mete la plata donde entró — `101` Caja si fue efectivo, `1041`
  Cuentas corrientes si fue tarjeta, billetera, transferencia o cheque. Una
  venta al crédito (`credito_empresarial`) **no asienta nada**, que es lo
  correcto: la plata no llegó y la cuenta por cobrar sigue viva.
  El asiento del cobro no pasa por las plantillas del PCGE ni por
  `regla_asiento`, a propósito: la cuenta del debe la decide el medio de pago
  y no el evento, y una venta se cobra con varios a la vez (mitad efectivo,
  mitad Yape). Ninguna plantilla de líneas fijas puede expresar eso.
- **Una venta anulada se quedaba con su ingreso asentado** (2026-09-05).
  `sales.venta_anulada` tampoco tenía suscriptor, así que el estado de
  resultados contaba una venta que no existió. Se reversa con el asiento
  inverso, que es como se deshace en contabilidad: nada se borra
  (RN-CTB-002). **Quitarle algunas líneas a una orden no reversa nada** —
  borraría el ingreso de las líneas que quedaron—; eso pide un asiento de
  ajuste por la diferencia y quedó anotado como deuda, igual que el
  incremento de una orden ya confirmada, que el dedupe del asiento descarta
  como si fuera un reenvío.
