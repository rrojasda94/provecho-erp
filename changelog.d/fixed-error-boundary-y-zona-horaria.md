- **Una pantalla que revienta ya no deja el ERP en blanco** (2026-08-30). No
  existía ningún error boundary: un throw al renderizar —el de
  `(app)/layout.tsx`, que pide la sesión, tumbaba la aplicación entera— caía
  en la pantalla por defecto de Next, que en producción es blanca y sin
  salida. En una tablet detrás de una barra eso se resuelve apagando el
  equipo. `frontend/app/error.tsx` vive en `app/` y no en `app/(app)/` para
  cubrir también PDV, KDS, asistencia, login y las rutas públicas, que
  cuelgan directo del layout raíz; reintenta con `reset()` y muestra el
  `digest`, que en producción es lo único que ata la pantalla al log. Costo
  aceptado: es uno solo y en paleta clara, así que reemplaza la pantalla
  entera y se ve fuera de tono sobre el PDV.
- **La fecha renderizada en el servidor salía cinco horas adelantada**
  (2026-08-30). El kardex de un SKU y la ficha de una devolución formateaban
  con `new Date(iso).toLocaleString("es-PE")`, y `"es-PE"` fija el idioma y
  no la zona: la ponía el proceso, que en Docker es UTC, así que un
  movimiento de las 20:00 se leía como la 01:00 del día siguiente. Ahora la
  zona viaja explícita en `frontend/lib/fechas.ts` —vale igual en el
  servidor, en `npm run dev` y en una tablet mal configurada— y
  `frontend/Dockerfile` fija `TZ` con `tzdata` como defensa en profundidad,
  porque alpine no trae la base de zonas y sin ella `TZ` se ignora en
  silencio. La fecha de cierre de un periodo contable dejó de mostrarse
  cortando el ISO con `slice(0, 10)`, que era el día UTC.
- **Cinco escrituras del backend leían el reloj del proceso** (2026-08-30).
  `movimiento.fecha_ejecucion`, `periodo.fecha_cierre` y
  `orden.fecha_emision` usaban `datetime.now()` a secas sobre columnas
  `timestamptz`; son instantes, así que pasan a `datetime.now(UTC)` como los
  otros 47 sitios. `venta.fecha_orden` —la que gobierna el correlativo
  diario— e `implementacion_material_sucursal.fecha` tenían
  `default=date.today` **sin paréntesis**: la función viajaba sin llamar y
  toda inserción que omitiera el campo (seeder, replay del hub, escritura
  directa del repo) fechaba en día UTC. El barrido de
  `tests/test_fechas_negocio.py` no las veía porque buscaba solo el literal
  `date.today()`; ahora cubre las tres formas y dice cuál usar en su lugar.
