- **El insumo que falta se crea desde el diálogo de importación** (2026-08-20,
  ADR-046 → ADR-052). Era parte de lo pedido en ADR-046 y nunca se entregó: la
  pantalla dejaba **elegir** uno existente u omitir la línea, y crear uno nuevo
  obligaba a irse a `/inventario/articulos`, crearlo a mano y volver a subir el
  archivo entero. Ahora el `<select>` viene con un botón «Crear» que abre un
  formulario en línea —código, unidad y tipo, con el nombre prellenado con el
  que trajo el archivo— y resuelve esa línea en todas las recetas que la
  nombran.
- **Cuatro lugares afirmaban que eso ya funcionaba.** El docstring de
  `importar-recetas.tsx`, el de `importacion_recetas.py`, la hoja de
  instrucciones de la plantilla y **RN-COM-031** decían "se elige cuál es, se
  crea, o se omite". `catalogoApi.crearArticulo` existía desde ADR-046 con un
  comentario que la describía como "alta rápida desde el diálogo de
  importación" y su único llamador era `contrato.test.ts`: código muerto con un
  comentario que describía una función inexistente. Los cuatro textos ahora
  describen lo que el código hace.
- Esto **no revierte** la alternativa que ADR-046 descartó: lo descartado era
  que el *importador* creara solo los insumos que faltan, porque un "Queso
  mozarela" mal tecleado se volvería un artículo duplicado que después hay que
  fusionar a mano. Que lo cree una persona, viendo el nombre que trajo el
  archivo, es lo contrario de autocrear.
- Mismo patrón para las **categorías** desconocidas al importar artículos:
  elegir, crear, o dejar el artículo sin categoría. Una **unidad de medida**
  desconocida no se crea desde acá a propósito —define cómo se cuenta el stock,
  y necesita categoría, ratio y decimales—: se informa para que se cree en su
  pantalla.
