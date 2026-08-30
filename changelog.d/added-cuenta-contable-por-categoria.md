- **Nada del catálogo se podía asociar a una cuenta contable** (2026-08-30,
  ADR-086). `plantillas.py` escribía todo producto contra los mismos códigos:
  **toda venta acreditaba `7011` y toda compra debitaba `6011` y `201`**, sea
  una pizza, una cerveza o la factura de la luz. Y como los estados
  financieros son pura agregación sobre `asiento_linea`, eso es literalmente
  lo que mostraba el balance. Había media solución sin terminar:
  `categoria.asiento_contable_config` existe desde la primera migración y era
  **de solo escritura** — sin tipar, sin validar, `CategoriaOut` no lo
  devolvía, ninguna pantalla lo escribía y `accounting` nunca lo leyó.
  Ahora la categoría es donde se configuran las cuentas —es el único agrupador
  que comparten `articulo` y `producto_comercial`, así que alcanza para
  categorías, artículos, productos y servicios de una vez—, se hereda por el
  árbol `padre_id`, y el asiento automático **reparte el monto del evento por
  categoría**, una línea por cuenta distinta. Con pantalla en Inventario →
  Categorías, incluida la columna que dice cuáles están configuradas y cuáles
  heredan.
- **Comprar un servicio metía la luz en el almacén.** Nuevo tipo de artículo
  `servicio` (sin migración: `articulo.tipo` es un enum extensible por
  diseño). Su parte del asiento va a la 63x y **no escribe el bloque de
  destino** — el asiento cuadra igual porque `201`/`611` son un par del mismo
  importe. Una OC mixta asienta el destino solo por lo inventariable. Y deja
  de generar falsas alarmas: hasta hoy un artículo sin SKU escribía una
  `incidencia_inventario` por ítem y por compra, así que cada factura de luz
  dejaba una para revisar y descartar.
- **La jerarquía de categorías no se podía armar por la pantalla.**
  `crear_categoria` aceptaba `padre_id` desde siempre y **el router no se lo
  pasaba**, y `CategoriaOut` tampoco lo devolvía: el árbol solo existía si
  alguien tocaba la base.
- **Sin configurar nada, nada cambia.** Los casos que afirman el asiento de
  fábrica siguen verdes sin tocarse, y hay uno nuevo que lo afirma
  explícitamente: es la propiedad que hace este cambio desplegable.
