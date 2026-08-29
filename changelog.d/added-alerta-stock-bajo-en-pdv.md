- **El PDV avisa cuando un producto usa un insumo con poco stock**
  (RN-INV-013), sin bloquear la venta: `GET /carta` marca `stock_bajo` en
  cada producto/variante cuya receta tenga algún insumo en o bajo su
  `stock_minimo`, en el almacén de la sucursal. Reutiliza el umbral que ya
  existía en `stock.stock_minimo` — no se agregó ninguna columna nueva. El
  ícono es solo un aviso: el botón de venta nunca se deshabilita.
