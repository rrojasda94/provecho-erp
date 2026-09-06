- **`editar_sku` existe** (ADR-091). `PATCH /inventory/skus/{id}` corrige
  `codigo`, `codigo_barras` y `activo` con las mismas reglas de unicidad
  que `crear_sku` — un código de barras mal tecleado solo se corregía por
  SQL. El importador no cambia: sigue informando un código repetido como
  omitido, corregirlo sigue siendo la pantalla de a uno.
- **`id_interno` pasa de 4 a 8 caracteres**, en `articulo` y en
  `producto_comercial`. Sigue único en todo el grupo, no por empresa — un
  catálogo de trescientos artículos agotaba rápido el espacio de códigos
  de 4 caracteres compartido entre todas las empresas. Los códigos ya
  asignados no se tocan.
