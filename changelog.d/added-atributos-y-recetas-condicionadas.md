- **El catálogo pasa al modelo de Odoo: atributos, variantes y recetas
  condicionadas** (ADR-055, ADR-056, migración `e2b7c40d91af`).

  Hasta ahora cada combinación vendible era una fila de producto con su
  propia receta. Con el catálogo real de Charlie's eso no se sostiene: una
  `Pizza MitadxMitad Familiar` de 19 sabores por mitad son **361 productos y
  361 recetas**, y cambiar los gramos de jamón obliga a abrir 361 fichas.

  - **Seis tablas nuevas** en `sales` — `atributo`, `atributo_valor`,
    `producto_atributo_linea`, `producto_atributo_valor`,
    `producto_variante_valor`, `producto_exclusion` —, las cuatro primeras
    calcadas de `product.attribute*` de Odoo 18.
  - **Los tres modos de `create_variant`**: `siempre` (materializa todas las
    combinaciones), `dinamica` (al venderse la primera vez) y `nunca` (no
    genera filas; el valor solo cambia lo que se consume). Elegir bien es lo
    que hace la diferencia entre 361 filas y ninguna.
  - **`receta_item.aplica_valores`**: una línea de receta puede aplicar solo
    a ciertas combinaciones. La regla es la de Odoo —agrupar por atributo y
    exigir al menos un valor de cada grupo—, así que las 26 líneas del
    archivo de Charlie's entran como 26 líneas.
  - **`receta_item.unidad_medida_id`**: una línea puede expresarse en otra
    UdM de la misma categoría que el artículo (30 ml de aceite sobre un
    artículo que se lleva en litros) y se convierte por `ratio` al descontar
    y al costear.
  - **`receta.es_kit`**, `ref_externa` en artículo, receta, producto y
    atributo (idempotencia al reimportar desde Odoo), `categoria.padre_id`
    (categorías jerárquicas) y `producto_comercial.lienzo_pos`.
  - **Una sola cuenta** de merma y conversión (`consumo_de_linea`) para el
    descuento de stock y el costeo, que antes estaban escritas distinto.

  **La migración es solo aditiva**: ninguna columna existente cambia de tipo
  ni de nulabilidad. La imagen 0.6.0 corre contra este esquema sin enterarse,
  así que volver atrás es desplegar 0.6.0 y no hace falta downgrade.

  Nada del PDV, compras, contabilidad ni almacén cambia de comportamiento
  mientras no se carguen atributos: las 1537 pruebas de 0.6.0 pasan sin
  editar una línea.
