- **El campo de dirección es un solo `<input>`, no dos cajas** (ADR-072,
  supera la sección "Dos cajas, no una" de ADR-053). El buscador de Google
  vivía separado del campo de texto que en verdad se guardaba, y en la
  práctica se tecleaba en cualquiera de los dos indistintamente — solo uno
  de ellos dejaba algo anclado, y esa fue la causa raíz de los bugs de
  dirección de cliente de arriba. Ahora el `<input>` de siempre busca
  sugerencias mientras se teclea y las muestra en un desplegable propio, con
  teclado y ARIA de combobox. Se puede seguir escribiendo una dirección que
  Google no conoce, y sin clave de Google el campo sigue siendo el `<input>`
  de siempre — nada de eso cambió.
- **Una dirección guardada solo como texto se ancla sola al abrir la
  ficha**, con un geocode directo, y solo si el resultado es inequívoco (sin
  coincidencia parcial, con precisión de puerta, sin ser un distrito o país
  a secas). Anclar en silencio un punto dudoso sería peor que no anclar: hay
  plata atada a ese punto (ADR-054).
