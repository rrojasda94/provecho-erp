- **Un reporte se puede elevar, y queda el rastro de quién intentó qué**
  (2026-08-09, ADR-036). `reporte_escalamiento` salda RN-CTP-004 y RN-PRD-014,
  declaradas como deuda desde ADR-033: cadena supervisor → comercial →
  gerencia, un escalón por vez, con historial append-only por nivel. Siete
  endpoints nuevos bajo `/api/v1/reports` y dos permisos —`reports.escalar` y
  `reports.escalamiento_resolver`— separados por lo mismo que solicitar y
  aprobar un ajuste: quien eleva no es quien cierra.
- **Vive en `src/modules/reports/`, no en `shared`**, contra lo que decía
  `data-model.md` §6. Esa línea se escribió cuatro meses antes de que el módulo
  existiera; hoy la entidad tiene un solo escritor y un solo lector, y su
  lógica necesita `Area`, `AreaMiembro` y los resolutores de destinatarios, que
  `shared` tiene prohibido importar.
- **Ancla al `reporte_emitido`, no a la venta.** Los `venta_id` / `carrito_id` /
  `orden_produccion_id` del diseño original son lo que `referencia_tipo` +
  `referencia_id` ya guardan, para los nueve tipos y no para tres — y `carrito`
  ni siquiera existe como tabla. Anclar a la venta perdería la foto de datos,
  el nivel, el actor y la doble puerta de RN-REP-002.
- **A quién elevar, sin jerarquía organizacional**: el ERP no tiene
  `supervisor_id` ni nivel de rol, así que el escalón se resuelve con el
  encargado de turno (nivel supervisor) y las áreas Comercial y Gerencia. El
  seeder pone el rol `supervisor` dentro del área Comercial, así que **elevar
  puede caer en la misma persona**: es la organización de hoy, y el endpoint
  devuelve los destinatarios para que quien eleva lo vea en vez de suponer que
  llegó a otro.
