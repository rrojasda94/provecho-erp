- **Apertura y cierre de caja mostraban el texto montado sobre los campos**
  (2026-08-28). `.pdv-etiqueta` define márgenes verticales pero no declaraba
  `display`, y esos diálogos la usan sobre un `<label>`: en una caja inline
  los márgenes verticales **no aplican**. La regla equivalente existía en
  `globals.css` pero acotada a `.erp`, y el PDV vive fuera de ese layout
  (ADR-013), así que nada de los estilos de diálogo del back office llegaba.
- **El pie fijo del layout raíz tapaba la franja de acciones del PDV y la
  última fila del KDS** (2026-08-28). Se pintaba en todas las pantallas, y
  esas dos no tienen página que scrollear para destapar nada.
- **El PDV no cedía con la escala de letra** (2026-08-28). La columna del
  ticket estaba clavada en `24.5rem`: con `--font-scale` al máximo se comía
  más de media tablet y la carta se quedaba sin lugar. Ahora es un `clamp`. El
  cuerpo de los diálogos descuenta el encabezado en vez de un `70vh` suelto —
  en una ventana baja, el diálogo bloqueante de apertura dejaba su botón de
  confirmar fuera de la pantalla, con la caja sin abrir y sin forma de salir.
