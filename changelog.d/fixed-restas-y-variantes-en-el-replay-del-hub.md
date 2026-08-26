- **La venta que el hub tomó durante un corte llegaba a la nube sin sus restas
  ni sus valores de variante** (ADR-009). El lote sí las llevaba —
  `_items_a_dict` emite `sin_articulo_ids` y `valores_variante_ids` por línea,
  y `VentaItemSyncIn` las declara —, pero al reproducirla `_crear`
  (`src/modules/sales/application/sincronizacion.py`) armaba el ítem sin esas
  dos claves y `crear_venta` las leía como ausentes. Consecuencia: la nube
  descontaba el insumo que el plato no llevó (una "sin cebolla" quedaba
  cobrada pero no restada, RN-PRD-004) y una receta condicionada (ADR-056) no
  activaba ninguna línea, así que la mitad-y-mitad se descontaba mal. Las dos
  claves se pasan ahora con `it.get(...) or []`, porque los lotes emitidos
  antes de RN-PRD-004 / ADR-055 no las traen. No se revalidan contra receta ni
  catálogo: el replay entra con `numero_orden`, es decir `exigir_opciones=
  False`, y esa venta ya se preparó y se cobró. Prueba nueva en
  `tests/test_sync_motor.py`: un lote con resta y valor conserva ambos en la
  fila de la nube, y el stock replicado respeta la resta.
- **Lo mismo en los extras del ítem**, que el replay también rearmaba sin
  esas dos claves. Para poder pasarlas hizo falta propagar
  `exigir_opciones` hasta `_armar_extras` (`ventas.py`), que hasta ahora
  revalidaba el extra siempre. De paso se arregla un rechazo que ya
  existía: si alguien desvinculaba un extra, le bajaba el tope o le quitaba
  `es_extra` durante el corte, la nube rechazaba la venta entera —
  `"Pizza Clásica no admite el extra ..."` — pese a que la sucursal ya la
  había preparado y cobrado. Esas tres comprobaciones ahora corren solo con
  `exigir_opciones=True`, igual que los grupos (RN-COM-023) y los atributos
  (RN-COM-040), que ya se exceptuaban. Prueba nueva: el extra conserva su
  resta y la venta se reproduce aunque el vínculo ya no exista en la nube.
