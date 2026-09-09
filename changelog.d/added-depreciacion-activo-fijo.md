- **Depreciación mensual de activo fijo** (2026-09-09, PROC-CTB-010,
  ADR-098). No estaba modelada en absoluto — bloqueada históricamente
  porque no existía el módulo de activos. Barrido mensual (Celery beat,
  día 1) lee `assets.application.queries_publicas.activos_depreciables`
  (nuevo contrato público) y postea un asiento lineal por activo por mes
  (debe `6813`, haber `3913`), idempotente por `<activo_id>:<AAAA-MM>`.
  `activo_depreciacion` lleva lo acumulado; se detiene solo al llegar a
  `de_baja` o al depreciar el valor completo. Sin las cuentas 6813/3913
  importadas, queda como `asiento_omitido` (no bloquea nada).
