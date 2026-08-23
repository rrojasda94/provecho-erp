- **El catálogo de Odoo se convierte y se carga** (`scripts/odoo/`).

  Dos comandos: `convertir_catalogo` lee los cuatro exports de Odoo 18
  (`product.template`, `product.attribute` y dos de `mrp.bom`) y escribe seis
  libros numerados en el orden en que hay que subirlos, más un `INFORME.md`;
  `cargar_catalogo --simular` los recorre resolviendo cada referencia y
  deshace todo al final, para poder decir "esto entra limpio" antes de tocar
  staging.

  Sobre el catálogo real de Charlie's: 243 artículos, 217 recetas con 523
  líneas, 28 categorías en árbol, 6 atributos con 72 valores, 214 productos
  comerciales y 65 precios. Simulación en cero problemas.

  **No inventa datos de negocio**: los 28 gramajes que Odoo trae en cero
  quedan aparte para que alguien los llene. Sí corrige, y lo escribe todo en
  el informe: 17 artículos cuya unidad no era la que sus recetas consumen,
  4 nombres duplicados, 2 categorías cuya hoja chocaba, 28 vendibles sin
  receta (RN-PRD-001), líneas repetidas del mismo insumo, y los cuatro
  atributos de mitad que venían marcados para materializar 289 variantes por
  tamaño.

- **Una línea de receta acepta unidad propia y condición** en
  `recetas.agregar_item` (`unidad_medida_id`, `aplica_valores`, `orden`). El
  mismo insumo puede repetirse **si cada línea aplica a otra combinación** —
  que es lo que hace posible la pizza mitad-y-mitad—; lo que sigue rechazado
  es la misma condición dos veces. Una unidad de otra categoría de UdM se
  rechaza con un mensaje que lo dice (RN-UDM-001).

- **Las categorías cuelgan unas de otras** (`crear_categoria(padre_id=...)`),
  con tope de profundidad: la base no puede impedir un ciclo en una tabla que
  se apunta a sí misma, y recorrer la cadena sin límite cuelga el request.
