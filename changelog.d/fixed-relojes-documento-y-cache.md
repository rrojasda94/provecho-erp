- **Dos sitios dejan de hardcodear `"America/Lima"`**:
  `rrhh/application/pad_asistencia.py` (de donde lo heredaba
  `avisos_asistencia.py`) y `core/celery_app.py`, que fija la zona de todos
  los `crontab()`. Los dos leen ahora `settings.zona_horaria`. El guard de
  `tests/test_fechas_negocio.py` gana un cuarto patrón prohibido para que
  no vuelva a colarse.
- **`purchases/comprobantes.py` deja de truncar sobre UTC crudo**.
  `func.date(Comprobante.created_at)` comparaba contra fechas que el
  usuario piensa en hora Perú — un comprobante registrado pasadas las
  19:00 caía del lado equivocado del filtro por fecha.
- **La consulta de DNI/RUC se cachea, con TTL de 5 minutos** (ADR-095). El
  alta consulta el mismo documento dos veces (botón «Buscar» +
  revalidación al guardar, ADR-041, que sigue igual); ahora solo la
  primera le paga al proveedor.
- **El 8/11 del documento deja de estar escrito a mano**: nueve sitios del
  frontend pasan a `tipoPorLargo`/`documentoValido` de `lib/documento.ts`,
  incluido un `documentoValido` local en el PDV que sombreaba al importado
  y no aceptaba documento vacío.
