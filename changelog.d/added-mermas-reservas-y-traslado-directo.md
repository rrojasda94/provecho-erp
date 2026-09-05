- **Mermas: la pantalla que le faltaba a tres endpoints con ADR propio**
  (2026-09-04, auditoría del 2026-08-30 §13). `POST /inventory/mermas`,
  `GET /mermas` y `POST /mermas/{id}/resolver` existían desde ADR-028, con
  pruebas y permisos sembrados, y **ningún llamador**: apartar mercadería
  inservible solo se podía hacer llamando la API a mano. Ahora
  `/inventario/mermas` la aparta (almacén, SKU, cantidad, motivo) y muestra
  la bandeja de resolución con «Desechar» —sale del stock y se asienta como
  pérdida— y «Reintegrar». Dos pasos y dos permisos distintos porque la
  segregación es la regla: quien declara que algo no sirve no firma su baja.
- **Reservas: por fin se ve de quién es el stock apartado, y se puede
  soltar** (2026-09-04). La columna «Reservado» de Stock decía cuánto y no
  había forma de saber por qué ni de liberarlo: `GET /inventory/reservas` y
  `POST /reservas/{id}/liberar` no tenían llamadores, así que
  `inventory.liberar_reserva` era un permiso sembrado que nadie podía
  ejercer y una reserva colgada de un requerimiento viejo mantenía stock
  fuera del disponible para siempre. Las mermas se listan pero no se liberan
  desde acá: se resuelven en su pantalla, donde la firma es de otro.
- **Traslados: recepción por línea, entrega parcial y traslado directo**
  (2026-09-04). La recepción mandaba `{items: [], parcial: false}` clavado,
  así que el camión que trae la mitad no tenía cómo declararse y quien
  recibía firmaba sin ver qué traía el envío —`GET /transferencias/{id}` era
  otro endpoint sin llamadores—. Ahora el diálogo carga el detalle **antes**
  de abrir, precargado con lo enviado, con casilla de entrega parcial: sin
  marcarla, lo que falte se registra como diferencia (RN-INV-002). Y se
  agrega el **traslado lateral**, de un almacén a otro sin requerimiento
  previo, que el backend admitía desde el slice original y no tenía por dónde
  crearse: era la sucursal que le presta harina a la de al lado, resuelta sin
  registrar nada.
- **Fuera de alcance, anotado como deuda**: la guía de remisión (tres
  endpoints, permiso propio, 14 pruebas, cero pantalla) es un bloque aparte
  —un documento con numeración, transportista y validez tributaria—, no un
  botón más en la tabla de traslados.
