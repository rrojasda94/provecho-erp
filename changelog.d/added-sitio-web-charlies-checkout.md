- **Carrito y checkout en el sitio de Charlie's Pizzas, PR3** (2026-09-17,
  ADR-105). Carrito en el navegador, checkout de invitado o con
  cuenta, dirección de entrega con la ubicación del navegador o local
  elegido para recojo, boleta o factura, y pago en efectivo o Izipay. Al
  confirmar, el pedido se asigna automáticamente a la sucursal más cercana
  dentro del radio de delivery, salvo que esté saturada, y muestra un
  estimado de espera según cuántos pedidos tiene esa sucursal en curso.

- **Canal `web` en `venta`.** `sales.domain.rules.CANALES` admite ahora
  `web` (antes solo `pdv`, `agente_ia`, `delivery`) — un pedido del sitio
  se confirma como una `Venta` real, con el mismo motor de precios y
  promociones que cualquier otro canal. El vínculo entre el pedido del
  sitio y la venta del ERP es un evento (`storefront.pedido_web_confirmado`
  → `sales.pedido_web_procesado`), nunca un import directo entre módulos.

- **Efectivo o Izipay, sin exigir caja abierta a la pasarela.** Un pedido en
  efectivo se cobra al entregar/recoger, con el flujo normal de caja; uno
  con Izipay se cobra de inmediato y no depende de que haya un turno de
  caja abierto en el punto de venta web — el dinero ya lo tiene la
  pasarela. Por ahora Izipay corre con un adaptador de prueba que aprueba
  cualquier cobro: falta la cuenta de comercio real para completarlo.
