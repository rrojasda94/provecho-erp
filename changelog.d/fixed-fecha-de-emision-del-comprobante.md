- **El comprobante declaraba la fecha de cuando se envió, no la del cobro**
  (2026-08-25, ADR-066 §7). `_documento()` ponía `datetime.now(UTC)` como
  `fecha_Emision`, con dos errores encimados: un comprobante que se quedó en la
  cola —proveedor caído, worker muerto, `FACTILIZA_TOKEN` sin configurar— y
  salía al día siguiente le declaraba a SUNAT **una fecha que la venta nunca
  tuvo**; y `now(UTC)` corría el calendario, porque una venta de las 20:00 en
  Tarapoto es del día 25 pero en UTC ya es 26 (la misma trampa que documenta
  `shared.fechas`). Ahora es `comprobante.created_at` leído en `America/Lima`.
  Salió a la luz al armar el QR: la cadena codifica la fecha de emisión, y con
  dos fechas distintas el papel y el XML no se pueden contrastar, que es
  justamente para lo que el fiscalizador escanea el QR.
