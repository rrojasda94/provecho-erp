- **Quien abría el KDS quedaba encerrado** (2026-08-28). Las pantallas de
  cocina viven fuera del shell del ERP y sus enlaces solo cruzan entre ellas,
  así que un trabajador que entraba desde el lanzador de módulos no tenía
  ningún camino de vuelta: la única salida era el botón atrás del navegador o
  teclear la URL. Se agrega "Salir" en las cuatro pantallas. El despacho
  embebido en el PDV no lo lleva y sigue cerrándose con su ×: desde un overlay
  un enlace que navega fuera descartaría el pedido a medio armar.
- **Con una comanda larga no se alcanzaba el botón de listo** (2026-08-28). La
  tarjeta no tenía techo y la lista de ítems no scrolleaba, así que "Todo
  listo" quedaba al fondo de una tarjeta de varias pantallas y el cocinero
  tenía que arrastrar la página entera con las manos ocupadas. Lo destapó la
  propia 0.8.0: las notas de cocina agregan un bloque por línea. Ahora la
  tarjeta tiene techo, solo scrollea la lista y el pie queda siempre a la
  vista; y las tarjetas dejan de estirarse entre sí, que era lo que empujaba
  los botones de toda una fila por culpa de una sola comanda.
