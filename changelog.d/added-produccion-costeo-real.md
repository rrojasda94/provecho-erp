- **El costeo "automático" de producción lo tipeaba el cliente** (2026-09-09,
  bloque `feat/produccion-costeo-real` del plan de deuda de producción,
  RN-PRD-018). `registrar_consumo` recibía `costo_unitario` desde el cliente
  en vez de leer `articulo.costo_promedio`, y `peso_desperdicio_real` se
  guardaba sin contrastarlo nunca contra `receta_item.merma_pct` — la
  comparación que la regla exige literalmente. Ahora: sin `costo_unitario`
  explícito, la línea se costea al `costo_promedio` vigente
  (`inventory.application.queries_publicas.costo_promedio_de_articulos`);
  nuevo `GET /ordenes/{id}/consumo-sugerido` explota la receta BOM del
  artículo escalada a `cantidad_planeada` (misma cuenta que
  `recetas.costo_linea`, para que "cuánto sugiere producción" y "cuánto
  cuesta la receta" nunca puedan divergir); `GET /ordenes/{id}` devuelve los
  consumos reales con `desviacion_desperdicio`; `orden.costo_teorico_insumos`
  queda de snapshot al registrar el consumo para esa comparación al
  completar. `consumo_produccion_item.unidad_medida_id` (nullable, mismo
  criterio que `receta_item`) permite teclear la cantidad en otra UdM de la
  misma categoría (RN-UDM-005) — se guarda ya convertida a la del artículo.
- **La tarifa de mano de obra de producción era global en el `.env`**
  (mismo bloque, ADR-014/068). `production_costo_hora_mano_obra` vivía en
  `src/config/settings.py` en vez de `parametro_empresa`, a diferencia del
  resto del ERP — Gerencia no podía cambiarla sin un redespliegue. Nuevo
  `production/application/tarifas.py::costo_hora_mano_obra_de` lee
  `parametro_empresa` `production/costo_hora_mano_obra` (mismo patrón que
  `sales.application.tarifa_delivery`), con el valor del `.env` como semilla
  mientras nadie apruebe una propuesta.
