- **El campo de dirección nunca mostró el buscador de Google, en ninguna
  pantalla** — sucursales, empresas, almacenes, proveedores, personas, PDV y la
  landing pública—, aunque la clave estuviera bien puesta y el SDK bajara
  completo. `cargarMaps` resolvía en cuanto existía `window.google.maps`, pero
  ese objeto aparece **antes** de que el bootstrap de `loading=async` termine
  de definir `importLibrary`: quien lo recibía moría con
  «maps.importLibrary is not a function». Ahora se espera a que `importLibrary`
  exista de verdad, que es lo único que se le pide al SDK. De paso se sondea en
  vez de escuchar `load`, porque un `<script>` que ya terminó de cargar no
  vuelve a emitir ese evento y reusarlo —lo que pasa en cada recarga en
  caliente— dejaba la promesa esperando para siempre.
- **El fallo era invisible**: el `.catch()` de `CampoDireccion` no decía nada,
  así que «sin clave», «clave restringida a otro dominio» y «el SDK cargó y el
  buscador reventó» se veían los tres como un cuadro de texto pelado. Ahora
  escribe el motivo en la consola. Es la lección de ADR-068 §3 en su forma más
  cara: una degradación pensada para no romperle la venta al cajero terminó
  escondiendo un bug propio durante meses.
- **La landing armaba los cinco campos `ubicacion_*` a mano** en vez de usar
  `ubicacionDe()`, y mandaba la latitud y la longitud como texto — exactamente
  la sexta copia que el docstring de ese helper anticipaba.
