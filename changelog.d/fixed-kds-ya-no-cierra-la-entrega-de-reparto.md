- **Despachar un pedido delivery desde el KDS hacía desaparecer su ruta**
  (2026-09-17, ADR-101). `delivery` escuchaba `sales.venta_entregada` para
  cerrar sola la `entrega` desde cualquier estado — si la ruta seguía en
  la calle, la parada saltaba a `entregada` sin que el repartidor hiciera
  nada; si el pedido todavía no tenía ruta, salía para siempre de "sin
  asignar". Se quitó ese listener: cerrar una entrega es ahora solo del
  repartidor (o de despacho en su nombre, desde `/delivery`); el botón del
  KDS pasa a llamarse "Despachar" y ya no toca el reparto. Costo aceptado:
  la venta puede quedar `entregada` en `sales` un rato antes de que
  `delivery` confirme el reparto — mismo trato que ya tenían los dos
  caminos convergentes de ADR-098, ahora en un solo sentido.
- **Cancelar una ruta y volver a crearla con la misma venta chocaba con
  `uq_entrega_venta`.** La entrega quedaba `pendiente` (correcto), pero
  contaba como "ya ruteada" para el tablero y `crear` insertaba una fila
  nueva en vez de reusar la existente. `pendiente` deja de contar como
  ruteada, y `crear`/`editar_paradas` reusan la fila que ya tenía la
  venta.
