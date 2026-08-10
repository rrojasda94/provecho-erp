- **Un reporte decía qué pasó y no quién ni dónde exactamente** (2026-08-09,
  ADR-036). `reporte_emitido` gana `actor_id` y `almacen_id`, y el catálogo de
  emisiones declara `clave_actor`: qué campo del payload es el actor. Ocho
  eventos de `inventory`, `accounting` y `production` lo publican ahora
  (ampliación aditiva). `sales.pedido_demorado` queda **sin actor a
  propósito**: lo detecta un barrido de Celery, y poner ahí al mozo que tomó
  el pedido convertiría un aviso de proceso en una acusación contra quien no
  provocó la demora. Un test parametrizado congela la lista de emisiones sin
  actor, para que la próxima se declare en vez de perderse en silencio.
- **Los reportes anteriores a este cambio dicen «Sistema»**: las dos columnas
  son nullable y **no hay backfill**. Un reporte de agosto no puede decir quién
  lo provocó porque el dato nunca se guardó, e inventárselo sería peor que
  dejarlo vacío (RN-REP-009).
- **`inventory.ajuste_fuera_margen` publicaba menos de lo que `events.md`
  decía**: la doc prometía `sku_id, diferencia, margen` y el código mandaba
  solo `ajuste_id` y `almacen_id`, así que el reporte decía «ajuste fuera de
  margen» sin decir de qué ni de cuánto. Ahora viajan `sku_id`, `cantidad`,
  `motivo` y `aprobado_por`, y la fila de `events.md` dice la verdad.
