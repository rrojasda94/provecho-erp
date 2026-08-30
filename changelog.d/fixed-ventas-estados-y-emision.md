- **El filtro de estados de la jornada de ventas mentía en silencio**
  (2026-08-30, auditoría del 2026-08-20 §1). El desplegable de `/ventas`
  ofrecía `entregada` —que es estado de **ítem**, del KDS, no de venta— y
  filtrar por ella devolvía siempre cero filas sin ningún error: el endpoint
  aceptaba `estado: str` libre y lo metía crudo en un `IN`. Al mismo tiempo
  faltaba `facturada`, que es donde termina casi toda venta cobrada en cuanto
  SUNAT acepta el comprobante, así que la mayoría de la jornada no era
  filtrable. Ahora los cinco estados salen de una fuente única en el dominio
  (`sales.domain.rules.ESTADOS_VENTA`), de la que también se arma el `Enum` de
  la columna y el `Literal` del query param: un valor inexistente responde 422
  en vez de una lista vacía, y un test de coherencia impide que la lista de la
  pantalla vuelva a separarse del enum.
- **La alerta de pedido demorado no disparaba para el caso más común**
  (2026-08-30). `ESTADOS_VIVOS` era `("confirmada", "pagada", "facturada")` y
  `confirmada` **no existe** entre los valores de `estado_venta`: faltaba
  `orden`, que es exactamente el pedido enviado a cocina con la cuenta todavía
  abierta —una mesa cualquiera—, y también `cerrada`, el consumo de personal.
  Los tests no lo veían porque todos creaban la venta ya `pagada`. Es el mismo
  defecto que el punto anterior y lo cierra la misma constante.
- **Tres botones de la jornada prometían un 403** (auditoría §3, parcial).
  «Reintentar emisión», «Nota de crédito» y «Anular» se dibujaban para
  cualquiera con `sales.leer`, que es lo único que la pantalla exige para
  cargar. Ahora se gatean con `sales.emitir_comprobante`,
  `sales.emitir_nota_credito` y `sales.cobrar` **o** `sales.anular`
  respectivamente —el OR es el mismo criterio del endpoint, donde el cajero
  cobra sin anular y el supervisor anula sin cobrar—, con el `tienePermiso`
  que ya usaba la ficha de orden de compra. Quien no puede reintentar sigue
  viendo el estado de emisión y el motivo del rechazo, que es la información
  útil de la celda. La autorización real la sigue haciendo la API.
- **Un fallo al traer las líneas para la nota de crédito se veía como una
  venta sin líneas** (auditoría §11, parcial). `lineasDeVentaAction` hacía
  `catch { return [] }`: con la API caída, el diálogo se quedaba en «Cargando
  las líneas...» para siempre y el único camino que ofrecía era acreditar a
  ciegas. Ahora devuelve el error y el diálogo distingue los tres casos —
  cargando, falló, y la venta de verdad no tiene líneas.
