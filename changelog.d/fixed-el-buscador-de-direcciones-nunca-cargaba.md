- **El buscador de direcciones no volvía tras una recarga en caliente.** El
  arreglo de la carga del SDK que salió en 0.8.1 (ADR-072) colgaba el sondeo
  del evento `load` del `<script>`, y un `<script>` que **ya** terminó de
  cargar no vuelve a emitirlo: reusar el existente —lo que pasa en cada
  recarga en caliente, porque la promesa memoizada es del módulo y se reinicia
  con él— dejaba la promesa esperando para siempre. Ahora el sondeo arranca de
  una y `load` no participa; el `error` del `<script>` sí sigue cortando.
- **El fallo era invisible**: el `.catch()` de `CampoDireccion` no decía nada,
  así que «sin clave», «clave restringida a otro dominio» y «el SDK cargó y el
  buscador reventó» se veían los tres como un cuadro de texto pelado. Ahora
  escribe el motivo en la consola. Es la lección de ADR-068 §3 en su forma más
  cara: una degradación pensada para no romperle la venta al cajero terminó
  escondiendo un bug propio durante meses.
- **La landing armaba los cinco campos `ubicacion_*` a mano** en vez de usar
  `ubicacionDe()`, y mandaba la latitud y la longitud como texto — exactamente
  la sexta copia que el docstring de ese helper anticipaba.
