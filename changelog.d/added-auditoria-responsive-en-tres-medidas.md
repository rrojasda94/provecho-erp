- **Una prueba que recorre el ERP en teléfono, tablet y PC**
  (`frontend/uso/responsive.spec.ts`). No compara píxeles contra una imagen de
  referencia —eso se rompe con cada cambio de copy— sino que afirma las dos
  cosas que sí son bugs: que ningún control quede dibujado fuera de un
  contenedor que lo recorta (una opción que existe y no se puede tocar) y que
  todo diálogo modal quede centrado. Recorre el home, las ocho pantallas de
  inventario, el KDS con una estación de preparación y otra de despacho, y el
  PDV con caja abierta y un pedido en cola, abriendo además cada diálogo que
  la pantalla sepa abrir. Encontró los cinco fallos de esta entrega y ninguno
  era visible en el ancho de escritorio, que es el único en el que se
  desarrolla.
