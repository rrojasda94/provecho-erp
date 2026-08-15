- **Las claves foráneas se hacen cumplir en todo el suite** (2026-08-15). SQLite
  las trae **apagadas** y Postgres no las apaga nunca: el suite dejaba pasar en
  verde borrados e inserciones que la base real rechaza —así estuvo meses roto
  `anular_lineas` contra `fk_venta_item_padre`—. Un listener del evento
  `connect` de SQLAlchemy en `tests/conftest.py` enciende
  `PRAGMA foreign_keys=ON` en **cualquier** engine SQLite del proceso, en vez
  de fixture por fixture: son ~75 y una que se olvide reabre el agujero.
  Corolario para escribir tests: un `uuid.uuid4()` en una columna FK ya no
  pasa, hay que sembrar la fila. Destapó cinco violaciones, dos de ellas bugs
  de producción de verdad.
- **Una receta con insumos no se podía borrar** (2026-08-15). `eliminar_receta`
  borraba las líneas y después la cabecera, pero sin `relationship` entre
  `receta` y `receta_item` SQLAlchemy no sabe que una depende de la otra y
  emitía el `DELETE` del padre **primero**: Postgres lo rechazaba por
  `fk_receta_item_receta_id_receta` y el usuario veía un 500. Como toda receta
  real tiene insumos, la operación estaba rota entera. Se fuerza el flush entre
  los dos borrados; hacerlo cumplir en el esquema (`ON DELETE CASCADE`) queda
  como deuda junto con el caso gemelo de `venta_item`.
- **El reporte que no se podía ubicar era el único que no se emitía**
  (2026-08-15). `reports.emision` guardaba en `almacen_id`, `sucursal_id`,
  `empresa_id` y `actor_id` el id que venía en el payload **aunque esa fila ya
  no existiera** — un almacén dado de baja, un usuario desactivado entre el
  hecho y su emisión (el bus despacha post-commit, ADR-016). Las cuatro son FK:
  el `INSERT` moría y se perdía el reporte completo, justo el que había que
  investigar. Ahora la columna queda nula y el id sobrevive en `datos`, que es
  lo que se lee al investigar: se pierde el enlace, que es exactamente lo que
  dejó de existir.
