- **Desechar un lote no conforme no dejaba ningún rastro contable**
  (2026-09-09, bloque `feat/produccion-desecho-a-contabilidad` del plan de
  deuda de producción, ADR-100). `completar_orden_produccion` con resultado
  `no_conforme_desechado` registraba `merma_cantidad`/`merma_motivo` en la
  orden pero nunca disparaba un asiento — el balance nunca se enteraba de la
  pérdida. No se reusó `inventory.merma_registrada`: esa merma opera sobre
  una reserva de stock de un artículo que ya está en el almacén, y el
  producto terminado de una orden desechada nunca llegó a existir como
  stock (solo se publica `orden_completada` en el caso `conforme`). Nuevo
  evento propio `production.orden_desechada` con su plantilla PCGE
  (`6599`/`201`, mismo circuito que la merma de mercadería): el monto es el
  costo de los insumos que la orden ya había consumido — la mano de obra
  queda afuera porque ya se reconoce aparte, como gasto de planilla.
  Reproceso sigue sin generar merma ni asiento, como siempre.
