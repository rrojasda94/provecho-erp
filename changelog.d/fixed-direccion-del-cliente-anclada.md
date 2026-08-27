- **La dirección de un cliente se guardaba sin su pin, y el delivery siempre
  se cotizaba a tarifa base** (ADR-072). `POST /sales/clientes` recibía las
  cinco columnas de ancla que ADR-053 diseñó y el router las tiraba sin
  pasarlas al caso de uso; `GET /sales/clientes/buscar` tampoco las devolvía.
  El PDV no tenía manera de reusar el pin de un cliente ya registrado, así
  que el reparto se cobraba siempre en línea recta o a tarifa base, nunca por
  la ruta real. Se reconectó la cadena de punta a punta: alta, búsqueda y la
  copia de texto+ancla juntos al asignar un cliente a un pedido.
- **El cliente jurídico no tenía dónde anclar su dirección.** Su domicilio
  vivía mezclado en `contacto` —el mismo campo que también hacía de teléfono
  o correo de quien coordina—. Ahora `cliente.direccion` es una columna
  propia, con las cinco de `UbicacionMixin`; `contacto` no se toca y las
  filas viejas se leen con `direccion or contacto`.
- **El SDK de Google Maps se daba por cargado antes de estarlo.**
  `lib/google-maps.ts` confiaba en el evento `load` del `<script>`, pero con
  `loading=async` ese evento llega antes de que Google adjunte
  `importLibrary` al namespace. La primera llamada reventaba con
  `TypeError: ... is not a function`, atrapada por un `.catch` silencioso a
  propósito (ADR-053) — así que el campo se quedaba sin buscador y nadie lo
  notaba: era indistinguible de "sin clave". Afectaba igual al widget viejo.
  Se arregló sondeando hasta que `importLibrary` existe de verdad antes de
  resolver.
