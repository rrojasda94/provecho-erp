- Corregido: el desplegable de empaque de la ficha de producto ofrecía **el
  catálogo entero** —insumos, mercadería, repuestos, suministros— en vez de
  solo los artículos de tipo empaque, así que `empaque_id` podía terminar
  apuntando a la harina y cada venta la descontaba como si fuera una caja de
  pizza. El faltante recién aparecía en el conteo del mes.
- El filtro faltaba en tres capas y ninguna defendía a la siguiente: el
  endpoint de artículos no ofrecía filtro por tipo, la pantalla no lo aplicaba
  y el `PATCH` metía `empaque_id` en un bucle `setattr` genérico sin mirar
  qué le estaban dando. Ahora **el backend valida** al crear y al editar
  (tipo `empaque`, no archivado), que es donde el dato malo hace daño.
  `data-model.md` ya declaraba «FK articulo tipo=empaque»: la restricción
  existía escrita, no ejecutada.
- `GET /inventory/articulos` acepta `?tipo=`. El filtro va en la base y no en
  la pantalla porque la lista viene paginada de a 50: con el catálogo real,
  filtrar lo que llegó dejaría el desplegable **vacío** en cuanto los
  empaques caigan fuera de la primera página, y un desplegable vacío no dice
  «faltan», parece que no hay empaques.
- El editor de recetas dejó de ofrecer empaques, repuestos y suministros como
  insumo. RN-EMP-003 dice que el empaque **no** va en la receta —se descuenta
  por modalidad desde el producto comercial—, así que ponerlo ahí lo
  descontaba dos veces.
- Contrato público nuevo `inventory.queries_publicas.articulo_resumen`:
  identidad y tipo de un artículo, para que otro módulo valide que el que le
  mandaron sirve sin entrar a su ORM.
