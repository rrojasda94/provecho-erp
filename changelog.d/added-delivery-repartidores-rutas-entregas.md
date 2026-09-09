- **El reparto propio tiene código** (ADR-098): repartidores con cuenta y
  vehículo, tablero de despacho, y el ciclo completo de una ruta —crear
  con ruteo heurístico, editar paradas, iniciar, entregar o fallar cada
  parada, reintentar o cerrar la fallida, finalizar o cancelar la ruta.
  `delivery` nunca importa el dominio de `sales`: marca la venta entregada
  publicando `delivery.entrega_registrada`, que un listener nuevo de
  `sales` traduce a la misma `cumplimiento.registrar_entrega` del botón
  "Entregar" del KDS, y al revés escucha `sales.venta_entregada`/
  `venta_anulada` para cerrar o cancelar su entrega sola. Costo aceptado:
  sin ruteo real contra Google, sin GPS, sin enlace público de seguimiento
  y sin avisos por WhatsApp todavía — quedan para los próximos slices
  (`docs/roadmap/deuda/modulo-delivery.md`).
