- **El lote de una orden de producción nacía siempre sin vencimiento**
  (2026-09-09, bloque `feat/produccion-lote-trazabilidad-auditoria` del plan
  de deuda de producción). El listener de `inventory` sabía leer
  `fecha_vencimiento`/`lote_codigo` del payload de `production.orden_
  completada` desde ADR-015 — `production` simplemente nunca los mandaba, así
  que FEFO trataba todo lote de fabricación propia como FIFO (RN-VNC-001).
  `POST /production/ordenes/{id}/completar` ahora acepta `fecha_vencimiento`,
  `lote_codigo` y `trazabilidad` (JSONB libre: manipulador, envasador, línea,
  variables de proceso — RN-LOT-002/003), que se persisten en la orden y
  viajan en el evento cuando el resultado es `conforme`.
- **El módulo no dejaba rastro de quién hacía qué.** Cero llamadas a
  `auditoria.registrar` en todo `production`, incluido cerrar una orden con
  desecho — acto de plata y de autoridad por definición. Las tres
  operaciones (crear, registrar consumo, completar) ahora auditan con
  `datos_antes`/`datos_despues` y la IP del request.
- **Un reintento de red podía duplicar el consumo o cerrar la orden dos
  veces.** Solo `crear_orden_produccion` era idempotente; `registrar_consumo`
  y `completar_orden_produccion` ahora aceptan una `idempotency_key` opcional
  — con la misma clave, la segunda llamada devuelve la orden tal como quedó
  en vez de volver a procesarla.
  Costo aceptado: la ficha de detalle y el formulario de completar en el
  frontend todavía no ofrecen estos campos (queda en
  `feat/produccion-ficha-y-consumo-sugerido`); por ahora son capacidad de
  API, usable por integraciones o por curl.
