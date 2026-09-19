- **El efectivo en la web exige cuenta; un invitado paga con Izipay**
  (2026-09-19). Un invitado que elige efectivo ve un aviso que lo invita a
  registrarse (el carrito se conserva) y no puede confirmar; la API también lo
  rechaza. Motivo: nadie a quien reclamar en un pedido contra entrega sin
  identificar. RN-WEB-013, ADR-105 §2 enmendado. Costo aceptado: quien no tiene
  tarjeta ni billetera no puede pedir sin registrarse.

- **Pantalla de pago de Izipay y webhook, con pasarela de prueba** (2026-09-19).
  Antes "pagar con Izipay" aprobaba en el acto, sin pantalla ni webhook, así
  que el tramo más riesgoso del cobro real jamás se ejercitaba. Ahora el
  pedido queda pendiente en `/pedido/{id}/pago` y la venta se crea recién
  cuando el webhook (`POST /storefront/webhooks/izipay`) aprueba el pago:
  nada llega a cocina sin pagar; un pago rechazado cierra el pedido sin
  venta; el webhook es idempotente. Sin credenciales de Izipay, la pantalla
  ofrece aprobar o rechazar el pago de prueba (solo fuera de producción; en
  producción sin credenciales Izipay no se ofrece). Cuando lleguen las
  credenciales solo cambia `IzipayReal`. RN-WEB-016, migración `8131c2cb30d2`.
