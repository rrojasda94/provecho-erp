- **Toda dirección del ERP se elige en un mapa** (2026-08-22, ADR-053,
  migración `c3d8b1f47a95`). Una dirección era `String(255)` en seis lugares y
  nada más: nadie validaba que existiera, nadie podía navegar hacia ella y el
  repartidor recibía una cadena que podía decir "por el mercado, casa azul".
  Ahora `UbicacionMixin` le suma `place_id`, latitud/longitud (6 decimales,
  ~11 cm), plus code y distrito a `sucursal`, `almacen`, `empresa`, `persona`,
  `proveedor` y `venta`. El campo único
  (`components/direccion/campo-direccion.tsx`) autocompleta con Places, muestra
  el punto en un mapa y deja arrastrar el pin para corregir la puerta cuando
  Google la deja a media cuadra.
- **La dirección escrita a mano sigue valiendo, y ese es el caso que se
  prueba.** En Tarapoto hay calles que Google no conoce, en el hub offline de
  una sucursal no hay internet y la clave se puede quedar sin cuota un martes a
  las ocho. Sin `GOOGLE_MAPS_BROWSER_KEY` el campo es el `<input>` de siempre y
  el ERP se comporta **exactamente** como antes de este cambio — lo verifica
  `frontend/uso/direccion.spec.ts`, que corre **sin** clave a propósito. Mismo
  criterio que ADR-005 y ADR-041: la integración prellena, no decide.
- **Editar el texto a mano suelta el pin**, en el servidor
  (`shared/ubicacion.py`) y de paso en la pantalla. Corregir "Jr. Lima 200" por
  "Jr. Lima 400" sin volver a elegir en el mapa dejaría las coordenadas de la
  puerta vieja: el texto diría una calle y el reparto iría a otra, cobrando la
  distancia equivocada. Ante la duda se pierde el pin —que se vuelve a poner en
  dos clicks— y no la verdad. No alcanzaba con la convención de PATCH del ERP
  (`None` = no tocar): justamente por esa convención, un formulario que corrige
  el texto sin ancla nueva no puede pedir el borrado.
- **La dirección de delivery del PDV por fin se guarda.** Se tecleaba en caja y
  se perdía: vivía solo en el borrador del navegador y `venta` no tenía columna
  que la recibiera (`referencia_atencion` es "para quién es el pedido", 50
  caracteres, no adónde va). Ahora viaja a `venta.direccion_entrega`, sube por
  el contrato de sync del hub offline y se imprime en la comanda, que es el
  papel que sale con el repartidor.
- **Anonimizar una persona también le borra el punto en el mapa** (Ley 29733,
  ADR-011). Las coordenadas de la casa de alguien son tan personales como su
  dirección escrita, o más: un punto no admite la ambigüedad de un "por el
  mercado". Sin esto la anonimización dejaba la puerta exacta en la base.
- **La CSP suma hosts de terceros por primera vez.** El mapa lo dibuja el
  navegador con una clave restringida por dominio, porque los tokens de sesión
  de Places —lo que hace que una búsqueda se cobre como una y no como ocho— los
  maneja el elemento oficial de Google y no tienen versión server-side. Se
  aceptó abrir `connect-src`, `img-src`, `font-src`, `style-src`, `script-src`
  y `worker-src` a la lista de Google **recortada a lo que este ERP usa**: sin
  Street View y **sin `'unsafe-eval'`**, que Google recomienda por las dudas.
  Queda pendiente verificarlo en el navegador con clave puesta (deuda
  transversal).
- **La clave del navegador baja por contexto y no es `NEXT_PUBLIC_*`.** La lee
  el proceso de Next y el layout la pasa una vez, así que se cambia reiniciando
  el contenedor en vez de reconstruyendo la imagen — la misma razón por la que
  se eliminó `NEXT_PUBLIC_API_URL`. Paso a paso de la consola de Google Cloud
  en `docs/engineering/integraciones-google.md`.
