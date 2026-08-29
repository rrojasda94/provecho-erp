- **Los comprobantes de una cuenta dividida ya se pueden imprimir todos**
  (2026-08-28). Cada cuenta separada emitía el suyo desde ADR-018, pero el PDV
  solo sabía pedir `GET /ventas/{id}/comprobante`, que devuelve el primero: el
  cajero cobraba dos cuentas y podía imprimir un solo papel, así que el
  segundo cliente se quedaba sin el comprobante por el que se había separado
  la cuenta. Se agrega el plural y el pie del diálogo de cobrado ofrece uno
  por cuenta, rotulado con su serie y correlativo. No se emite un comprobante
  por **pago**: un pago parcial no tiene líneas propias que declarar a SUNAT,
  y repartirlas sería inventar un detalle que nadie consumió.
