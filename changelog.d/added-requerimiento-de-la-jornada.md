### Added

- **Requerimiento de la jornada** (`inventory`, ADR-051, RN-INV-023/024): el
  local abre `/inventario/solicitudes` y encuentra una lista ya armada con lo
  que está bajo su punto de reorden (`stock_minimo`), la edita, suma lo que
  necesite aunque no esté bajo mínimo —queda marcado como pedido del local,
  no como urgencia— y la envía para aprobación. Nuevo estado `borrador`
  (uno por almacén) en `solicitud_insumos` y columna `bajo_minimo_al_pedir`
  en `solicitud_item`, estampada al agregar cada ítem.
- **Toma de inventario con pantalla propia**: `/inventario/conteos` cubre lo
  que la API ya tenía desde ADR-019 y ningún formulario ofrecía — abrir,
  contar a ciegas, cerrar viendo los ajustes generados, anular con motivo.
  Suma `GET /inventory/conteos`, que faltaba.
- `GET /inventory/solicitudes`, `GET /inventory/conteos` y
  `GET /inventory/conteos/programa` filtran por `sucursal_id` y `marca_id`,
  resueltos por join a través del almacén.
