- **El pedido no siempre llegaba al KDS, pero los aumentos sí** (2026-08-28).
  Dos agujeros distintos en la misma consulta, los dos reportados como uno.
  La cola de cocina filtraba `estado in ('orden','pagada')`, y
  `emitir_comprobante` pasa la venta a `facturada` en cuanto Factiliza acepta
  —segundos después del cobro—: el pedido para llevar que se cobra de una
  sola vez podía desaparecer de la pantalla antes de que la cocina llegara a
  verlo. En una mesa no pasaba, y por eso los aumentos parecían funcionar:
  solo existen sobre una orden abierta. Ahora la cola mira la misma lista que
  el historial y lo que saca un pedido es **entregarlo**, no cobrarlo. El
  segundo agujero: una línea cuya categoría no estaba en ninguna estación
  quedaba invisible en todo el KDS —`pendiente` para siempre, y el pedido
  nunca entregable— con el aviso que lo explicaba viviendo en una pantalla a
  la que ese pedido jamás llegaba; ahora la atiende la primera estación de la
  cadena. Se aceptó que la cola muestre más pedidos a la vez: era comida sin
  preparar que ya no se veía. ADR-078.
- **Un aumento reintentado mandaba dos comandas a cocina** (2026-08-28). El
  alta de la venta era idempotente desde siempre; el aumento no. Una
  respuesta que se perdía y su reintento dejaban dos comandas idénticas que
  nadie podía distinguir de un pedido real de dos rondas.
  `venta_item.idempotency_key` marca la primera línea de cada envío —lo
  idempotente es el envío entero, no la línea— y el campo es opcional en el
  contrato para no romper a los clientes que ya estaban mandando aumentos.
