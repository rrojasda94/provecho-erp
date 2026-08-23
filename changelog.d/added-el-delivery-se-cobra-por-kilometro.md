- **El reparto propio se cotiza por distancia real** (2026-08-22, ADR-054,
  migración `d41f6a2c98b7`). Con las direcciones ya ancladas en el mapa
  (ADR-053), `POST /sales/ventas/cotizar-delivery` devuelve kilómetros de
  manejo, cuánto sale llevarlo (`base + precio × km`) y si conviene derivarlo.
  El PDV lo muestra en el diálogo de tipo de orden, antes de aceptar el pedido.
- **El cálculo NO sale del navegador.** Define cuánta plata paga el cliente, y
  un número que viaja por el navegador es un número que se puede editar. Lo
  mide la Routes API desde el servidor, con una **segunda clave restringida por
  IP** (`GOOGLE_MAPS_SERVER_KEY`) — son dos claves porque Google no admite
  restringir la misma por referente HTTP y por IP a la vez. De ahí sale un
  invariante verificable: si aparece una llamada a `routes.googleapis.com` en
  la pestaña de red del navegador, está mal hecho.
- **Google caído no impide vender.** Se cae a distancia en línea recta
  (haversine × 1,3) marcada `aproximada`, que el PDV muestra como "aprox.".
  Cobrar de menos por un kilómetro es preferible a no poder tomar el pedido, y
  es además lo único que funciona en el hub offline de una sucursal (ADR-009).
  El `1,3` es una perilla de calibración, no una constante: se ajusta
  comparando cotizaciones aproximadas contra las reales.
- **Pasado el radio, o en distrito vetado, se sugiere DAZ DAZ.** Es un aviso al
  cajero y no una integración: quien decide es la persona, y si acepta se marca
  el campo que **ya existía**, `venta.repartidor_externo_plataforma`
  (`rappi|ubereats|pedidosya|dazdaz`). Cero tablas nuevas. La zona restringida
  se evalúa **antes** de medir: no depende de la distancia, y preguntarle a
  Google costaría una llamada por una respuesta que ya se sabe.
- **Las zonas vetadas son una lista de distritos, no polígonos.**
  `DELIVERY_DISTRITOS_RESTRINGIDOS` se compara sin tildes ni mayúsculas contra
  el distrito que ya viene con la dirección. PostGIS resolvería zonas de verdad
  y traería una extensión, un tipo de columna y una pantalla para dibujar
  polígonos: es mucha máquina para una lista de cuatro nombres (queda en la
  deuda del módulo).
- **Lo cotizado se congela en la venta.** `venta.distancia_entrega_km` y
  `venta.costo_entrega` se guardan al crear la orden y no se recalculan: la
  tarifa cambia y el pedido de ayer no puede cambiar de precio — el mismo
  criterio por el que la guía de remisión congela sus direcciones. El replay
  del hub **no vuelve a cotizar**: esa venta ya se cobró con un precio.
- **La cotización tiene cuota**, por usuario y por IP, reusando el mismo
  mecanismo que la consulta de DNI/RUC (ADR-041). Cada llamada gasta una
  medición de un proveedor pago y un bucle mal escrito en el PDV se come el
  plan del mes. Se suma un `@lru_cache` sobre la medición, con las coordenadas
  redondeadas a ~1 m: cada pedido se cotiza dos veces —la que ve el cajero y la
  que congela la orden— y así paga una sola llamada. Va sobre la medición y no
  sobre la cotización completa para que un fallo de Google **no** quede
  cacheado.
- **Arranca apagado**: `DELIVERY_TARIFA_BASE`, `DELIVERY_PRECIO_POR_KM` y
  `DELIVERY_DISTANCIA_MAXIMA_KM` valen `0` de fábrica y el delivery se sigue
  cobrando como antes hasta que el negocio defina la tarifa.
- Costo aceptado: **el reparto se calcula, se guarda y se muestra, pero todavía
  no suma al total de la venta** ni aparece en el comprobante. Cobrarlo de
  verdad exige una línea de venta sobre un producto de servicio "Delivery", con
  su IGV y su cuenta contable — radio de impacto mucho mayor que el resto de
  este cambio. Queda declarado en la deuda del módulo `sales`.
