- **El back office deja de vestirse de afiche y se viste de mesa de trabajo**
  (ADR-037). El brandboard de julio se aplicaba por igual a todo: crema de
  pared a pared y cada `h1`–`h4` en Anton itálica y VERSALES. Es la voz
  correcta cuando la marca le habla al cliente —PDV, KDS, carta— y la peor
  posible en una pantalla de trabajo: la itálica en versales es el ajuste
  menos escaneable que existe, y sobre crema las tarjetas blancas pierden
  contraste justo donde están los números. Ahora son **dos voces**: acero,
  Archivo condensada y tinta en el back office; crema, Anton y brasa en PDV,
  KDS y login. Los hex se movieron por contraste medido, no por gusto: el
  naranja `#F4511E` daba 3.4:1 sobre blanco con `text-primary` en 41 lugares
  y pasa a `#C6390F` (5.3:1); el lima `#AEEA00`, que en la práctica era el
  color de ~30 insignias de estado, era ilegible en texto y amarillento en
  insignia, y pasa a verde `#17864B`.
- **La tabla y el diálogo dejan de parecer HTML de 1998**, y con ellos 45
  pantallas que no se editaron. El buscador de `TablaDatos` (28 pantallas) era
  un `<input>` **sin una sola clase de estilo** y el estado del orden un
  `" ↑"` concatenado al texto — el "parece más HTML que elementos
  interactivos" de ADR-035, replicado 28 veces. Suma encabezado pegajoso,
  atajo `/`, filas fantasma mientras carga, vacío que distingue "no encontré"
  de "no hay", selector de tamaño de página, y `meta.numero` para alinear
  cifras a la derecha en monoespaciada tabular: una columna de importes con
  ancho proporcional obliga a leer dígito por dígito para comparar dos filas,
  y comparar dos filas es a lo que se viene a un ERP. `DialogoFormulario` (17
  pantallas) gana backdrop desenfocado, entrada con escala, y encabezado y pie
  fijos con el cuerpo scrolleable — un formulario de doce campos dejaba
  «Guardar» fuera de la pantalla. Las dos mantienen la firma de props
  compatible hacia atrás.
- **Los emoji de los módulos salen**; entran íconos de trazo (`lucide-react`,
  ya instalado). Cada sistema dibuja un emoji distinto —el 🍕 de una tablet
  Android no se parece al de Windows— y doce emoji de colores en la grilla del
  home compiten entre sí. El home además agrupa por área de negocio en vez de
  escupir catorce fichas iguales.
- **Un acento, no una paleta por área.** Se probó un color por área de negocio
  (`--area-*`) y se descartó: ADR-013 §8 ya había rechazado el color por
  módulo o por tarjeta, y cuatro tintes son el mismo arcoíris con menos pasos.
  Las áreas sobreviven como agrupación del home; ordenar no necesita pintar.
