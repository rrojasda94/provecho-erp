- **Un artículo sin SKU dejaba el inventario inerte, y en silencio** (2026-08-31).
  `stock` y `movimiento_inventario` cuelgan de `sku_id`, no de `articulo_id`,
  así que un artículo sin SKU no tiene existencias que ver, no entra en un
  conteo y la recepción de una compra lo saltea anotando una incidencia
  `sin_sku` que nadie mira — mientras la OC igual pasa a `recibida` y la
  pantalla dice que todo salió bien. Nada lo impedía: ni el alta ni la
  importación masiva creaban uno, y la hoja «SKUs» de la planilla es
  opcional. En staging entraron así 244 artículos y el módulo entero parecía
  roto: stock vacío en todos los almacenes, conteos imposibles y dos compras
  recibidas que no movieron una sola unidad. Ahora `crear_articulo` garantiza
  el SKU (RN-PRD-006) con el `id_interno` de código, el importador lo agrega
  al que no declare ninguno, y la migración `12f51f21f27e` repara los que ya
  existan. Los servicios siguen sin SKU a propósito: no tienen existencias.
  Los tests que cubrían la recepción pasaban en verde porque el fixture
  armaba el SKU a mano — se agregó el que recorre la forma real: dar de alta
  el artículo por la API y recibirle una compra.
