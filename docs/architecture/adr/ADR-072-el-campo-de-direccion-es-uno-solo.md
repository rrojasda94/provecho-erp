# ADR-072 — El campo de dirección es uno solo, y el cliente por fin ancla

- **Estado:** aceptada
- **Fecha:** 2026-08-27
- **Contexto:** `components/direccion` (frontend), `sales` (cliente, PDV)
- **Relacionado:** ADR-053 (la dirección se elige en el mapa — esta ADR
  supera su sección "Dos cajas, no una"), ADR-054 (el delivery se cobra por
  kilómetro), ADR-005 y ADR-041 (integraciones que prellenan sin bloquear)

## Contexto

Un cliente se registraba con dirección y esa dirección se guardaba **solo
como texto**. Al volver a cargar ese cliente en el PDV para un delivery, el
reparto se cotizaba siempre a tarifa base, sin distancia: `POST
/sales/clientes` recibía los cinco campos de ancla que ADR-053 diseñó, y el
router los tiraba sin pasarlos al caso de uso. `GET /clientes/buscar`
tampoco los devolvía — construía la respuesta con el ancla en `null` siempre.
El cliente jurídico, además, no tenía ni dónde guardar un ancla: su
dirección vivía mezclada en `contacto`, el mismo campo que servía de
teléfono o correo de quien coordina.

La causa de fondo no era un olvido aislado: era el diseño de "dos cajas" que
ADR-053 eligió a propósito. El buscador de Google vivía **arriba** del
`<input>` de texto, como una pieza aparte que solo servía para escribir el
texto y mover el pin; el campo de verdad, el que viaja en el formulario, era
el de abajo. En la práctica, quien tecleaba una dirección lo hacía en
cualquiera de las dos cajas indistintamente —eran dos rectángulos con el
mismo propósito visible—, y solo una de ellas dejaba algo anclado. El
resultado, mirado desde afuera, era indistinguible de un bug: "aquí no
funciona el autocompletado".

## Decisión

### Una sola caja

Se elimina el `PlaceAutocompleteElement` de Google. El `<input>` de siempre
—el que ya tenía `name`, `defaultValue` y los cinco ocultos de ADR-053—
ahora es también el que busca: mientras se teclea, pide sugerencias a
`AutocompleteSuggestion.fetchAutocompleteSuggestions` y las muestra en un
desplegable propio (`ListaSugerencias`), con teclado, ARIA de combobox y
resaltado, igual que cualquier otro buscador con autocompletado del ERP
(`PersonaPicker`).

Los tokens de sesión de Places, que ADR-053 citaba como la razón para no
tocar el widget oficial, ahora los abre y cierra el propio código
(`buscador-lugares.abrirBuscador`): uno por sesión de tecleo, hasta que se
pide el detalle de un lugar elegido. El modelo de facturación no cambia —una
búsqueda entera sigue cobrándose como una—, solo el código que lo maneja.

**Lo que "dos cajas" protegía de verdad no eran dos cajas — era la salida de
emergencia.** Esa se conserva intacta: **se puede escribir una dirección que
Google no conoce y guardarla igual.** En Tarapoto hay calles así, y el alta
no puede depender de que un tercero conteste (mismo criterio que ADR-005 y
ADR-041). Un canal de Google que no traiga `AutocompleteSuggestion` — el
`v=weekly` puede ir por delante de los tipos instalados — hace que el campo
se degrade al mismo `<input>` pelado de siempre, sin romper nada. Sin clave,
sin internet, o con la clave sin cuota un martes a las ocho de la noche, el
ERP se comporta exactamente igual que antes de ADR-053. `direccion.spec.ts`
sigue verificando ese caso sin clave, y ahora además comprueba que sin SDK el
campo **no** lleve el `role="combobox"`: no hay combobox posible sin lista.

Sigue valiendo, sin cambios, la regla que ADR-053 fijó: **editar el texto a
mano suelta el pin.** El backend manda (`shared/ubicacion.py`); esta ADR no
la toca.

### Una dirección guardada como texto se ancla sola

Al abrir un campo con texto y sin ancla —el caso de todo lo que se registró
antes de este cambio, y todo lo que se corrija a mano de ahora en más—, se
hace un geocode directo. Se ancla **solo si el resultado es inequívoco**:

- no es un `partial_match` (Google casó solo parte del texto);
- la precisión es `ROOFTOP` o `RANGE_INTERPOLATED` — se rechaza
  `GEOMETRIC_CENTER` (centro de una calle: puede quedar a cientos de metros
  de la puerta y *parece* anclado, que es lo peor cuando se cobra por
  kilómetro) y `APPROXIMATE` (centroide de una zona);
- el tipo del resultado no es un distrito, una provincia o un país a secas.

Ese criterio vive en `lib/direcciones.esConfiable`, aparte del componente y
sin SDK, para poder probarlo sin hablarle a Google. Si no califica, no pasa
nada: el registro se queda sin pin hasta que alguien lo vuelva a escribir y
elija una sugerencia.

**El texto no se reescribe.** El geocode solo deduce el punto; la dirección
que escribió una persona sigue siendo la que se ve. Esto además es lo que
hace que el backend no confunda esto con una corrección: al no cambiar el
texto, `desanclar_si_cambio_el_texto` no encuentra motivo para soltar el pin
recién puesto.

Se agrega un `Map` de módulo (tope 50 entradas) para no repetir el geocode
cada vez que el diálogo de delivery del PDV se remonta con el mismo pedido.

### El cliente jurídico gana dirección propia

`cliente` suma una columna `direccion` y el `UbicacionMixin` — las mismas
cinco columnas que ya tenían `persona`, `proveedor`, `sucursal`, `almacen` y
`empresa` desde ADR-053. `contacto` no se toca: sigue siendo el teléfono o
correo de quien coordina, nunca la dirección, y las filas que ya existen se
leen con `direccion or contacto` hasta que alguien edite la ficha. Sin
backfill — mismo criterio que ADR-053: un geocode masivo se cobra por
registro.

### Se reconecta la cadena de punta a punta

Tres puntos donde el ancla se perdía, ya sin relación con el diseño de la
caja:

- `POST /sales/clientes` ahora pasa los cinco campos de `ClienteCreate` al
  caso de uso, para natural y para jurídico.
- `GET /clientes/buscar` y `/clientes/listado` (misma función,
  `_cliente_buscado`) ahora devuelven el ancla: de `persona` si es natural,
  de `cliente` si es jurídico.
- El PDV copia **el texto y el ancla juntos** al asignar un cliente
  registrado a un pedido — copiar solo el texto, que es lo que hacía antes,
  es indistinguible del bug original: el reparto queda cotizando a tarifa
  base aunque el cliente sí tenga un pin guardado.

### El SDK avisaba que cargó antes de estar listo

Verificando esto con una clave real apareció un segundo bug, también
preexistente y sin relación con el diseño de dos cajas: `lib/google-maps.ts`
daba el SDK por listo cuando el `<script>` disparaba su evento `load`. Con
`loading=async` en la URL —que este mismo archivo pide a propósito para no
bloquear el render— ese evento llega **antes** de que Google termine de
adjuntar `importLibrary` al namespace: `window.google.maps` ya existe, pero
todavía no es utilizable. La primera llamada a `importLibrary` reventaba con
`TypeError: maps.importLibrary is not a function`, atrapada por el `.catch`
silencioso que ADR-053 pone a propósito (no puede romper el formulario) —así
que el fallo nunca se veía, ni en consola ni en pantalla: el campo
simplemente se quedaba sin buscador, indistinguible de "no hay clave".

Esto afectaba **igual** al `PlaceAutocompleteElement` de antes: llamaba a
`maps.importLibrary("places")` con el mismo patrón. No es un bug que esta
ADR haya introducido; es uno que esta ADR encontró al ser la primera vez que
alguien probó el campo con una clave real después de ADR-053.

Arreglo en `cargarMaps`: al recibir el `load`, sondear (hasta 4 segundos,
cada 20ms) hasta que `typeof window.google.maps.importLibrary === "function"`
sea cierto, y recién ahí resolver. Sin red extra: es la misma referencia de
objeto, solo se espera a que Google termine de completarla.

## Alternativas descartadas

- **Mantener el widget oficial y arreglar solo el backend.** Reconectar la
  cadena sin resolver la confusión de las dos cajas habría dejado guardando
  bien lo que alguien buscara en la caja de arriba, y sin ancla lo que
  alguien tecleara en la de abajo — el síntoma habría vuelto en cuanto
  alguien usara el campo "equivocado".
- **Un único campo, pero sin salida de texto libre.** Es lo que ADR-053 ya
  había descartado y sigue sin ser viable: hay calles que Google no conoce.
- **Backfill de las direcciones existentes con un geocode masivo.** Se
  prefiere el costo distribuido (una llamada por apertura de ficha, con
  cache) al costo de un lote que se cobra entero de una sola vez.

## Consecuencias

- Seis columnas nuevas y nullable en `cliente` (migración
  `bf0ea834a972`), sin tocar `contacto`.
- La CSP no cambia: los hosts de Google ya estaban abiertos desde ADR-053.
- Un SKU de Geocoding nuevo que antes solo se gastaba al arrastrar el pin:
  ahora también se gasta, con cache, al abrir una ficha con texto sin ancla.
- La sección "Dos cajas, no una" de ADR-053 queda **superada por esta ADR**;
  se deja anotado ahí, sin borrarla.
