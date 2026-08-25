- Corregido: en un producto con líneas de receta condicionadas (ADR-056,
  ej. una pizza MitadXMitad), `GET /productos/{id}/quitables` devolvía el
  mismo insumo una vez por cada línea condicionada que lo usaba ("sin
  aceitunas" repetido varias veces en el PDV). Se agregó `distinct()` a la
  consulta de `insumos_de_receta`.
