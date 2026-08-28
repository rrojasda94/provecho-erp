- **El aumento a una mesa abierta se confirma con "Enviar", y sale como
  comanda nueva** (2026-08-28, ADR-075). Antes la línea viajaba al confirmar
  el diálogo del producto —no al pulsar Enviar, que quedaba inerte en
  "Enviado" desde el primer envío—, así que marcar algo ya era mandarlo a
  cocina. Y el KDS agrupa por venta: el postre de las 21:40 aparecía en la
  misma pastilla que la entrada de las 20:15. Ahora la línea queda "Sin
  enviar" hasta que alguien toca **"Enviar aumento (N)"**, y `venta_item.tanda`
  hace que cada envío sea una tarjeta propia en las pantallas de preparación,
  con su propio reloj. Despacho sigue viendo el pedido entero: la bolsa se
  arma completa (ADR-044), y partirla en dos sería la forma de entregar media
  orden. Vale igual para mesa, para llevar y delivery.
- **Quitar un producto ya enviado pide motivo de verdad** (2026-08-28). El
  campo era obligatorio en el contrato y el PDV mandaba `"Anulado desde PDV"`
  en las mil anulaciones del año: el reporte de anulaciones lo leía y no decía
  nada. Ahora lo teclea quien quita, con chips para los cuatro motivos
  frecuentes, y se recuerda si el servidor termina pidiendo la firma del
  supervisor.
