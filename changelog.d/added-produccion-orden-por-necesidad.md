- **`production` prometía escuchar `inventory.stock_bajo_minimo` desde
  2026-07-25 y nunca lo hizo** (2026-09-09, bloque `feat/produccion-orden-
  por-necesidad` del plan de deuda de producción, RN-PRD-007/011). El
  README del módulo decía "Escucha: `inventory.stock_bajo_minimo` (dispara
  orden por necesidad)", pero no existía `production/application/
  listeners.py` ni ningún registro en `src/core/app.py` — el evento se
  publicaba desde 2026-08-06 y nadie del lado de producción lo procesaba.
  Ahora, al cruzar el mínimo de un artículo con receta BOM, si la empresa
  tiene **una sola** cocina de producción (almacén `tipo=produccion`) se
  crea sola una orden `borrador` con `origen=ajuste_por_necesidad` (columna
  nueva en `orden_produccion`; `creado_por` pasa a nullable porque esta
  orden no tiene ningún humano detrás — mismo criterio que `usuario_id`
  nulo en el propio evento, que el reporte muestra como «Sistema»).
  `cantidad_planeada` sale de `stock_minimo × factor_reposicion − cantidad`
  redondeado al rendimiento de la receta (produce en lotes completos, no
  una fracción de tanda); el factor vive en `parametro_empresa
  production/factor_reposicion` (semilla `2`, ADR-014/068). Es idempotente
  por SKU y día, y no crea una segunda orden mientras la primera siga sin
  cerrar control de calidad. Con cero o más de una cocina de producción no
  crea nada — ahí sigue quedando solo el aviso de `reports`, que es donde
  Gerencia decide a mano cuál de las cocinas produce.
