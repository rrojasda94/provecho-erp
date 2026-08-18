- **Los diecisiete diálogos del ERP se abrían pegados a la esquina superior
  izquierda, no centrados** (2026-08-18). Dos causas encimadas, y ninguna se
  ve leyendo el componente del diálogo. La primera: el preflight de Tailwind
  pone `margin: 0` en todos los elementos y con eso pisa el `margin: auto`
  con el que el navegador centra un `<dialog>` modal. La segunda: `.revelar`
  —la animación de entrada de cada pantalla— usaba
  `animation-fill-mode: both`, que deja la animación aplicada para siempre;
  el `transform` del último fotograma queda computado como
  `matrix(1, 0, 0, 1, 0, 0)`, que es la identidad pero **no es `none`**, y un
  `transform` no-`none` convierte al elemento en bloque contenedor de todo
  `position: fixed` que tenga debajo, incluido el top layer del diálogo. Se
  arregla con `dialog:modal { margin: auto; overflow: auto }` global y con
  `backwards` en lugar de `both` en las tres animaciones de entrada.
- **El PDV escondía el ticket entero por debajo de 60rem** (2026-08-18): el
  pedido, los totales, «Enviar» y «Cobrar» desaparecían con un `display: none`
  en toda tablet en vertical y en todo teléfono, sin nada que los reemplazara.
  Ahora la carta y el ticket comparten la celda y se alternan con el botón
  «Pedido»/«Carta» de la barra, que solo existe en ese ancho.
- **La barra del PDV recortaba «Cuentas» y «Cobrados» a 390 px**: no entraban
  en una línea junto al buscador y `.pdv` tiene `overflow: hidden`, así que
  las dos vistas quedaban dibujadas fuera de la pantalla sin scroll que las
  alcanzara. La barra ahora envuelve.
- **El conteo por denominaciones no entraba en el diálogo en un teléfono**: la
  grilla de dos columnas fijas se desbordaba llevándose «Abrir caja» con ella,
  y sin caja abierta no se vende. Pasa a una columna donde no entren dos.
- Las barras superiores del PDV y del KDS tenían la altura clavada en 56 px:
  el título envuelto a dos líneas se salía de la banda y se montaba sobre el
  contenido de abajo.
- **La pantalla de bloqueo del PDV se pintaba con el fondo blanco del
  navegador**: `.pdv-bloqueo` se monta como hermano de `<main class="pdv">`,
  donde los tokens `--pdv-*` no existen, y un `var()` sin respaldo invalida la
  declaración entera. Deuda declarada en ADR-050 y cerrada acá.
