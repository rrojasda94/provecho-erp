- **Producción no consolidaba un reporte de la jornada** (2026-09-09,
  bloque `feat/produccion-reporte-de-jornada` del plan de deuda de
  producción, RN-DOC-010). Nueva tabla `reporte_produccion`: consolida las
  órdenes que cerraron control de calidad ese día en un almacén
  (`merma_total`, `desperdicio_total`, `horas_hombre_total`,
  `costo_total`, snapshot `ordenes` JSONB); única por `almacen_id,
  jornada`. `generar_reporte_jornada` recalcula el existente mientras no
  esté visado (`visado_por`/`visado_at`) y deja de tocarlo en cuanto lo
  está — se visa, no se redacta. Nueva columna `orden_produccion.
  completado_at` (`updated_at` no servía: cualquier `flush` lo pisa antes
  de que la orden cierre). Barrido de Celery
  `production.generar_reportes_de_jornada_vencidos` (cada 15 min) genera
  el de cada almacén de producción pasada la `hora_cierre_jornada` de su
  empresa (`parametro_empresa`, semilla configurable) — la primera tarea
  periódica del ERP con hora de corte por empresa en vez de una hora de
  servidor fija. `POST /production/reportes-jornada/generar` hace lo
  mismo a demanda; `POST .../{id}/visar` es el único acto humano sobre el
  documento. Publica `production.reporte_produccion_generado` (sin actor,
  nivel `aviso`, distribuido a Gerencia y Cocina). Nuevo permiso
  `production.visar_reporte_jornada` (seeder + `jefe_cocina`) y pantalla
  `/produccion/reportes`.
