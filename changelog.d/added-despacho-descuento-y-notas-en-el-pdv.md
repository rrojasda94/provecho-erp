- **La cola de despacho se abre desde el PDV** (2026-08-28). El personal lo
  pidió: hoy vive en otra pantalla del local y hay que caminar hasta ella para
  saber si un pedido salió. Es un **overlay y no una navegación** —salir del
  PDV cierra la caja de la vista y descarta el pedido a medio armar—, y reusa
  el mismo componente de despacho en vez de dibujar una versión reducida: una
  segunda vista de la misma cola es una segunda vista que se desincroniza.
  Detrás de `kds.operar`.
- **Cupón y descuento manual, por fin en la caja** (2026-08-28). Los dos
  endpoints existían desde su slice y el PDV no los llamaba nunca. Van en un
  solo botón porque para el cajero son la misma pregunta —«¿por qué paga
  menos?»— pero **no se firman igual**: el cupón no lo autoriza nadie
  (RN-PRM-007, el cupón *es* la autorización) y el descuento manual lo firma
  un supervisor con su PIN (RN-COM-017). No se acumulan (RN-PRM-006): el que
  ya está aplicado se dice y el otro camino se apaga. El motivo es el catálogo
  cerrado que la API valida, no texto libre — un campo abierto no agrupa, que
  es para lo único que ese dato existe. `test_repo_coherencia` vigila que las
  dos listas no se separen.
- **Las notas de cocina llegan a la cocina** (2026-08-28, ADR-075). El diálogo
  del producto pedía una nota desde el primer PDV y el dato moría en el
  navegador: no había columna, no viajaba, y al releer la orden se perdía.
  Ahora `venta_item.nota` viaja, se pinta bajo su plato en el KDS y sale en la
  comanda. Se suma `venta.nota_cocina`, la nota **del pedido entero** —"servir
  todo junto", "bebidas al final"—, que va al pie de la pastilla y en todas
  sus tandas: es una instrucción del pedido, y la tanda que no la llevara la
  ignoraría sin saberlo. Se puede cambiar con la orden ya en cocina, que es
  cuando de verdad se pide.
