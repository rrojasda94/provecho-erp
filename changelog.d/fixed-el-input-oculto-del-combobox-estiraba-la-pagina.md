- **Una tabla con desplegables estiraba la página en teléfono y tablet**
  (2026-08-30). Base UI dibuja por cada `Combobox` un input oculto de
  validación con `position: absolute`, y el contenedor con `overflow-x-auto`
  de las tablas no estaba posicionado: sin ancestro posicionado, ese input
  toma como bloque contenedor el del documento y **el contenedor deja de
  recortarlo**. En Usuarios —donde cada fila lleva dos desplegables— eso
  ponía un elemento a 667 px en una pantalla de 390 y aparecía barra de
  scroll horizontal en la página entera, con la tabla ya corrida cuando se
  volvía. El contenedor pasa a ser `relative`, que no cambia nada de lo que
  se ve y devuelve el recorte a donde corresponde. Lo encontró la auditoría
  de `uso/responsive.spec.ts`, que hasta este parche nunca llegaba al final
  de su recorrido.
