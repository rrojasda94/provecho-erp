# Deuda técnica — Módulo accounting (slices siguientes)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-07-25 **Pago a proveedor (PROC-CTB-003)**: migración `cbf904a9fc1b`
  (`movimiento_dinero`). `purchases.comprobante_conforme` encola
  (`registrar_pago`, idempotente por `comprobante_id` RN-CTB-008);
  `ejecutar_pago` exige `accounting.pago_gestionar` + umbral vía
  `parametro_empresa` (código `pago_umbral`, RN-CTB-005, `accounting.pago_aprobar`
  sobre el umbral) y genera asiento vía `regla_asiento`
  (`accounting.pago_ejecutado`); `rechazar_pago` cierra sin ejecutar.
  Eventos `accounting.pago_ejecutado`/`pago_requiere_aprobacion` ya se
  publican, pero sin consumidor todavía (ver pendiente de `purchases`
  arriba y de `users`/alertas abajo).
- ⬜ **Resto de eventos → asiento automático**: `sales.pago_registrado`,
  `sales.comprobante_emitido`, `purchases.caja_chica_rendida`,
  `inventory.transferencia_recibida`, `inventory.merma_registrada`,
  `inventory.ajuste_fuera_margen` están documentados en `events.md` pero
  sus módulos de origen aún no los publican en código (o, en el caso de
  `sales`, el evento real ya publicado se llama `sales.venta_pagada`, no
  `sales.pago_registrado` — desalineación de nombre entre spec y código,
  revisar). Cuando existan, agregar su extractor de monto/empresa en
  `accounting/application/listeners.py`.
- ⬜ **Detracción SPOT sin cuenta propia**: `movimiento_dinero.monto_detraccion`
  se calcula (RN-IMP-003) pero el asiento de `pago_ejecutado` no la
  desglosa — el debe/haber usa el monto total, no separa la cuenta de
  detracciones del banco/caja. Requiere ampliar `regla_asiento` a N líneas
  (hoy es siempre 1 debe/1 haber).
- ⬜ **`accounting.pago_ejecutado`/`pago_requiere_aprobacion` sin
  consumidor real**: `events.md` documenta que `purchases` marca la OC
  pagada y que `users` alerta a Gerencia — ninguno de los dos escucha
  todavía.
- ⬜ **`rechazar_pago` no libera el comprobante**: el único
  `movimiento_dinero` por `comprobante_id` (unique) queda en `rechazado`
  para siempre; reintentar el pago del mismo comprobante requiere
  intervención manual (borrar/reabrir la fila) — evaluar si el negocio
  necesita un caso de uso de reapertura.
- ✅ 2026-07-26 **Arqueo backend (PROC-CTB-005)**: `application/caja.py::registrar_arqueo`
  + `POST /accounting/arqueos`, publica `accounting.arqueo_registrado`
  (slice mínimo, ver ADR-012 — sin visado de Gerencia ni plantilla propia).
- ⬜ **Conciliación bancaria (PROC-CTB-004)**: sin modelo ni caso de uso.
  RN-CTB-006 (cierre de periodo exige conciliación visada) no se valida
  todavía — `cerrar_periodo` hoy no lo comprueba. Bloquea implementar
  rigurosamente RN-CTB-006.
- ✅ 2026-07-26 **Ciclo de caja → eventos**: `apertura_caja`/`cierre_caja`/
  `arqueo` (PROC-CTB-001/002/005) ya tienen capa de aplicación
  (`accounting.application.caja`, ver ADR-012) y publican
  `accounting.apertura_caja_registrada`/`cierre_caja_registrado`/
  `cierre_caja_irregular`/`arqueo_registrado`. **No generan asiento
  contable todavía** (sin listener que consuma esos eventos hacia
  `regla_asiento`) — eso sigue pendiente. Tampoco incluye RN-POS-009..013
  completas ni la máquina de estados de `custodia_efectivo` — ver Deuda
  técnica → Dashboard y caja.
- ⬜ **Activo fijo/depreciación y flujo de caja** (PROC-CTB-007/010,
  propuestos): sin modelar, dependen de que exista el módulo de activos.
- ⬜ **`declaracion_itan`**: entidad documentada en data-model §8, sin
  slice propio (depende del ciclo tributario anual, RN-IMP-006).
- ⬜ **`regla_asiento` de una sola línea debe/haber**: el mapeo actual
  genera exactamente 2 líneas por evento (una cuenta debe, una haber) —
  suficiente para provisión/recepción/venta simples; un asiento con más de
  2 líneas (ej. IGV desglosado) requiere asiento manual o ampliar el mapeo.
