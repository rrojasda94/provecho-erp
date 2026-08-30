- **La cola de despacho abierta desde el PDV no decía cómo volver**
  (2026-08-30). El despacho se embebe como overlay a propósito (ADR-078):
  salir del PDV cerraría la caja de la vista y descartaría el pedido a medio
  armar. Pero para volver solo había una `×` sin etiqueta, flotando encima
  del encabezado del KDS —el componente embebido escondía sus tres enlaces,
  «Salir» incluido—, y el turno lo reportó como que el botón no existía. Que
  es lo que pasaba: el botón estaba y no decía a dónde llevaba. Ahora el
  encabezado del despacho embebido trae **una** salida con nombre, «Volver al
  PDV», en el mismo lugar donde el modo autónomo pone «Salir», y la `×`
  desaparece con su CSS. Dos salidas para lo mismo, una encima de la otra y
  la de arriba muda, era peor que una sola clara. De paso el seeder de e2e
  siembra una pantalla de despacho por sucursal: desde que el PDV la embebe
  no había ninguna, así que solo se podía probar su estado vacío.
