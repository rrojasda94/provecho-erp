- **El consumo de personal se cierra desde el PDV** (2026-08-30). La orden de
  comida del personal no muestra "Cobrar" —no se cobra— y su único cierre era
  la entrega desde la pantalla de despacho, así que en la práctica quedaba
  abierta y aparecía como cuenta pendiente en cada arqueo. Ahora el ticket
  tiene **"Cerrar cuenta"** en el lugar donde iría "Cobrar": llama a la misma
  entrega (`POST /sales/ventas/{id}/entrega`) y no a un cierre propio, para
  que un plato tenga un solo rastro. Sigue exigiendo que la cocina haya
  marcado todo listo: cerrar comida que ni salió sería mentirle al KDS.
- **Las cuentas cerradas del turno incluyen los consumos de personal**
  (2026-08-30). La pestaña "Cobrados" pasó a llamarse **"Cerradas"** y lista
  también las órdenes en estado `cerrada`, marcadas como consumo y con "—" en
  vez de S/ 0.00 — rotularlas "Cobrados" las contaría como venta, que es
  exactamente lo que el tipo de orden existe para evitar. Sin esto, la comida
  del personal desaparecía de "Cuentas" al cerrarse y no reaparecía en ningún
  lado: el turno no tenía dónde ver qué se preparó sin cobrar.
- **`sales.consumo_personal_registrado` es un reporte del catálogo**
  (2026-08-30). Llega a Gerencia y Contabilidad con el número de orden, el
  motivo y quién lo firmó — el evento ahora viaja con esos dos últimos datos.
  Era la deuda que ADR-034 dejó declarada: el consumo se leía a mano por
  `GET /sales/ventas?tipo=consumo_personal`.
