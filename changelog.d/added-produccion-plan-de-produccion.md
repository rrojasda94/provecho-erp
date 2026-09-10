- **Toda orden de producción se creaba suelta, sin plan** (2026-09-09,
  bloque `feat/produccion-plan-de-produccion` del plan de deuda de
  producción, RN-PRD-007/012). Nueva tabla `plan_produccion` (cronograma
  fijo por línea/turno, única por `almacen_id, fecha, turno,
  linea_produccion` — sin dos planes compitiendo por la misma línea al
  mismo turno del mismo día). `turno`/`linea_produccion` son texto libre,
  no un catálogo con FK: `turno_sucursal` (RRHH) está atado a una
  sucursal y una cocina de producción central no siempre tiene una.
  `POST /production/planes` crea el plan (`planificado`); `POST
  /planes/{id}/ordenes` le liga una `orden_produccion` nueva
  (`origen="plan"`); `POST /planes/{id}/iniciar` reserva los insumos de
  **todas** sus órdenes en `inventory` (`reserva_stock.tipo="produccion"`,
  el tipo que existía desde ADR-028 sin ningún productor, referenciada
  por `orden_produccion.id`) y pasa a `en_ejecucion` — si algo no
  alcanza, `StockInsuficiente` interrumpe `iniciar` entero, sin dejar
  reservas a medias; `registrar_consumo` cierra la reserva de la orden
  cuando el insumo sale de verdad; `POST /planes/{id}/cerrar` libera lo
  que ninguna orden llegó a consumir. Nuevo `GET/POST /production/planes`,
  `GET /planes/{id}`, permiso `production.planificar` (seeder + `jefe_
  cocina`), y `/produccion/plan` en el frontend. Pendiente: el listener
  de `inventory.stock_bajo_minimo` (`feat/produccion-orden-por-necesidad`)
  todavía no vincula la orden que crea al plan del día si existe uno.
