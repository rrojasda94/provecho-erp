- **Un delivery con cliente registrado no se podía enviar: "tipo de venta
  inválido: natural"** (2026-08-30). Al elegir el cliente, el PDV guardaba el
  objeto entero como ubicación del pedido (`ClienteBuscado` es
  `{...} & Ubicacion`, así que el tipo no se quejaba) y después lo esparcía en
  el cuerpo de la venta: viajaban también su `id`, su `nombre` y su `tipo`
  —`natural`—, que el servidor leía como tipo de venta. Ahora hay
  `soloUbicacion()` que recorta al ancla; el costo aceptado es tener que
  llamarla en cada asignación, porque el tipo estructural no lo puede exigir.
