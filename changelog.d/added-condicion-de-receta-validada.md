- **La condición de una línea de receta se valida contra el producto que la
  usa** (ADR-092). `agregar_item`/`editar_item` rechazan con 409 un valor
  que ningún producto de la receta ofrece — antes el único guardarraíl era
  la lectura conservadora de `aplica_a_variante`, que alcanzaba para no
  descontar de más pero dejaba pasar una receta mal armada sin avisar.
  Nuevo `sales.valores_ofrecidos_de_receta`. No retroactivo: lo ya guardado
  sigue leyéndose igual, y una receta que ningún producto usa acepta
  cualquier valor porque no hay contra qué compararlo.
