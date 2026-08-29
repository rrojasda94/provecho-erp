- **El cobro rechazaba el monto exacto** (2026-08-28). Eran dos cosas que se
  veían como una. La aritmética del diálogo se hace en el `number` de
  JavaScript, donde 33.30 − 10 deja 23.299999999999997; ese número viajaba al
  servidor tal cual, el pago entraba y la suma nunca llegaba al total, así que
  **la venta quedaba en `orden` y sin comprobante** — cobrada de hecho y sin
  cobrar para el sistema. En el otro sentido, un `pagado < total` por una
  millonésima dejaba "Confirmar pago" muerto con "Restante S/ 0.00" en
  pantalla. Del lado del servidor pasaba lo simétrico: `cantidad × precio`
  puede traer cuatro decimales, así que el saldo real era 18.525 mientras la
  pantalla —que lee `venta.total`, ya truncado— decía 18.53. Ahora la plata se
  redondea a centavos en un solo lugar, con `ROUND_HALF_UP` porque es como
  redondea `numeric` en Postgres: cuantizar distinto de la columna que guarda
  el total habría reabierto la misma grieta por el otro lado.
- **El diálogo de cobro calculaba el total en el navegador** (2026-08-28).
  Sumaba el borrador, así que no podía saber el flete de una orden reabierta
  ni el prorrateo del descuento entre cuentas, y cualquiera de las dos
  diferencias terminaba en un cobro rechazado con el "monto exacto" delante
  del cajero. Ahora lo pide a `GET /ventas/{id}/saldo`: el número que valida
  el pago tiene que ser el mismo que lo propone. Si la consulta falla se cobra
  igual con el total del borrador — quedarse sin poder cobrar por un dato de
  apoyo sería peor que la diferencia que ese dato evita.
