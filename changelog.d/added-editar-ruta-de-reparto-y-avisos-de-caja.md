- **Una ruta de reparto se gestiona de punta a punta** (2026-09-17,
  ADR-101). `PUT /delivery/rutas/{id}/paradas` ahora funciona con la ruta
  `planificada` **o** `en_curso` — agrega, quita paradas no resueltas y
  reasigna repartidor sin cancelar y crear de nuevo. El tablero
  (`/delivery`) gana Editar, Iniciar (deshabilitado si algo sigue en
  cocina), Finalizar y "Marcar entregada" por parada.
- **Se rutea desde que se toma el pedido, no desde que está listo**
  (RN-DLV-001). El despacho arma la ruta con lo que ya sabe que va a
  salir, y decide con qué de verdad sale recién al iniciarla — que sigue
  exigiendo todas las paradas `lista`. El tablero y la PWA del repartidor
  marcan "En cocina" lo que todavía no llegó.
- **Toast + sonido en KDS y caja cuando delivery registra una entrega o
  termina una ruta.** `GET /delivery/avisos` (sondeado cada 15 s, sin
  datos del cliente) más dos notificaciones de bandeja nuevas —
  `delivery.entrega_para_cobrar` (caja) y `delivery.ruta_finalizada`, que
  hasta ahora no tenía consumidor. Resueltas por permiso, no por rol
  (`users.usuarios_con_permiso`, contrato nuevo).
- **El mapa del tablero marca el sentido de la ruta con flechas.** La ida
  y la vuelta al origen se dibujaban superpuestas y sin indicar
  dirección, fácil de leer como "va en los dos sentidos" en una calle de
  sentido único.
