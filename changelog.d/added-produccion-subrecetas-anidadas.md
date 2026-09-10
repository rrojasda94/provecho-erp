- **`registrar_consumo` esperaba insumos ya disponibles en stock, sin
  resolver BOM de varios niveles** (2026-09-09, bloque
  `feat/produccion-subrecetas-anidadas` del plan de deuda de producción,
  RN-PRD-020). Nueva columna `orden_produccion.orden_padre_id`
  (autorreferencia nullable e indexada, sin tope de niveles — una
  subreceta puede colgar de otra, sin riesgo de ciclo porque una fila
  nueva no puede referenciarse a sí misma al crearse). `GET /ordenes/{id}/
  consumo-sugerido` marca `requiere_orden_hija` en la línea cuyo artículo
  tiene receta BOM propia y el almacén no tiene disponible suficiente
  (`inventory.application.reservas.disponible`); `POST /ordenes/{id}/
  ordenes-hijas` crea esa orden en el mismo almacén, con
  `origen="subreceta_anidada"`. La orden padre rechaza
  `registrar_consumo` con 409 mientras tenga una hija que no llegó a
  `conforme` — el insumo que la hija fabrica todavía no existe como stock
  real. Nueva ficha de detalle `/produccion/ordenes/[id]` (no existía
  ninguna): árbol padre/hijas y consumo sugerido con el aviso de orden
  hija requerida.
