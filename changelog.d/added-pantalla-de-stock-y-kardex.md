- **No había dónde ver los niveles de stock** (2026-08-30).
  `GET /inventory/stock` existe desde el primer slice, paginado y con filtro
  por almacén, y **ninguna pantalla lo consumía**: lo único que mostraba
  saldos era la ficha de un SKU, a la que solo se llegaba desde el reporte de
  stock bajo mínimo sabiendo de antemano cuál mirar. La pregunta con la que se
  abre el módulo —qué hay— no se podía responder. Ahora Inventario → Stock
  lista todo con dos vistas, por almacén y en general, y filtros por sucursal,
  almacén, categoría, texto y «solo bajo mínimo». El KPI del dashboard lleva
  ahí en vez de decir un número y dejarlo.
- **El stock viajaba como UUID pelados.** `StockOut` sumó `almacen`,
  `articulo`, `sku_codigo`, `unidad` y sus decimales (RN-GER-010). Resolverlos
  en el cliente obligaba a bajar el catálogo entero de SKUs y de almacenes
  para dibujar 50 filas — la petición que se rompe primero cuando el catálogo
  crece. Se componen solo para las filas de la página, como ya se hacía con
  las reservas.
- **El kardex se escribía y no se leía.** `movimiento_inventario` lleva el
  rastro de todo cambio de stock desde el primer slice y solo había `POST`:
  `MovimientoRepo.q_list` existía sin un solo consumidor. Ahora hay
  `GET /inventory/movimientos` (paginado, por almacén y por SKU, del más
  nuevo al más viejo) y la ficha del SKU muestra sus últimos 25. Sin esto la
  pantalla decía cuánto queda y nunca por qué.
