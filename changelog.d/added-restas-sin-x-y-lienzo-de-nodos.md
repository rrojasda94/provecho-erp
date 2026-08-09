- **Restas: "sin cebolla" ya mueve el inventario** (2026-08-09, ADR-035,
  RN-COM-028/RN-PRD-019, migración `a4f1d0c8b573`). `RN-PRD-004` manda aplicar
  los modificadores en el orden **tamaño → combinación → extras → restas**, y
  las restas eran el único tramo sin implementar: se escribían en la nota
  libre a cocina, el plato salía bien y **el inventario descontaba la cebolla
  igual**. Esa cebolla que se quedó en la cámara aparecía como faltante en el
  conteo del mes sin que nadie pudiera explicarlo.
  - `venta_item.sin_articulo_ids` (JSONB, nullable) guarda qué insumos no
    lleva la línea. Guarda `articulo_id` y **no** `receta_item_id` porque la
    línea de receta se edita y se borra, el artículo no: guardando la línea,
    una receta corregida mañana dejaría restas históricas apuntando a nada y
    la comanda reimpresa de una venta vieja diría "sin —". NULL = no quitó
    nada, que es lo que vale para todo lo ya vendido, sin backfill.
  - **Lo quitable es la receta**: `GET /sales/productos/{id}/quitables`
    devuelve los insumos del producto. No hay tabla ni flag de "quitables"
    que mantener — sería la misma verdad escrita dos veces, y dos datos que
    dicen lo mismo terminan diciendo cosas distintas. Pedir quitar algo que
    la receta no pone devuelve 409; el replay del hub se exceptúa (ADR-009),
    porque esa venta ya se preparó y la receta pudo cambiar durante el corte.
  - **No cambia el precio; sí el consumo.** Quitar cebolla no abarata la
    pizza, pero el insumo deja de descontarse, y la reposición por anulación
    o nota de crédito devuelve **solo lo que se consumió** — reponer lo que
    nunca salió dejaría stock de más en el conteo.
  - Cocina las ve: KDS en ámbar y comanda impresa (`SIN CEBOLLA`, sangrada).
    En el PDV son chips rojos y tachados junto a los extras; la nota libre
    sigue existiendo para lo que no es un insumo ("bien cocida").
- **Lienzo de nodos del producto comercial**
  (`/catalogo/productos/{id}/nodos`, 2026-08-09, ADR-035). El árbol completo
  de lo que se puede pedir en una pantalla —producto → tamaños → grupos (el
  sabor es uno) → extras → restas → empaque—, recorrible: al tocar los nodos
  se arma un plato y un panel recalcula en vivo la receta fusionada, el costo
  y el margen de esa combinación exacta. Antes había que abrir cinco
  pantallas y sumar a mano.
  - Eso **no es un modelo nuevo**: el tamaño ya era un producto hijo
    (RN-COM-022) y el sabor ya era una opción de grupo con receta propia
    (RN-COM-021/023). Lo que faltaba era verlo junto.
  - La fusión se calcula en el cliente y **no se guarda**: es un simulador.
    Lo que se descuenta de verdad sale del servidor al confirmar la venta.
  - Las cantidades de cada receta se siguen editando en Catálogo → Recetas,
    con enlace desde cada nodo (ADR-023 §4: el editor duplicado ya se reportó
    como confuso una vez).
- **Quitar un extra de un producto y borrar un grupo de opciones**
  (`DELETE /sales/productos/{id}/extras/{extra_id}` y
  `DELETE /sales/productos/{id}/grupos/{grupo_id}`). Cierra la deuda que
  ADR-023 dejó anotada. Borrar un grupo **suelta** sus extras en vez de
  borrarlos: el extra es un producto comercial con su receta y su precio, y
  existe con o sin grupo.
