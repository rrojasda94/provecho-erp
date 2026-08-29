# ADR-053 — La dirección se elige en el mapa, y el mapa lo dibuja el navegador

- **Estado:** aceptada
- **Fecha:** 2026-08-22
- **Contexto:** `users` (sucursal, almacén, empresa, persona), `purchases`
  (proveedor), `sales` (venta, cliente), frontend (CSP)
- **Relacionado:** ADR-004 (tenant), ADR-005 (integraciones que prellenan),
  ADR-009 (hub offline), ADR-011 (Ley 29733), ADR-041 (consulta de documento),
  ADR-054 (cobro del delivery por kilómetro)

## Contexto

Una dirección en Provecho era `String(255)` y nada más. Estaba en seis lugares
—`sucursal.direccion`, `almacen.direccion`, `proveedor.direccion`,
`persona.domicilio`, `empresa.domicilio_fiscal` y el campo de delivery del
PDV— y en todos era texto libre: nadie validaba que existiera, nadie podía
navegar hacia ella, y el repartidor recibía una cadena que podía decir "por el
mercado, casa azul".

El disparador concreto no fue la prolijidad: es que **sin coordenadas no se
puede cobrar el delivery por distancia** (ADR-054). Un texto no se puede medir.

Hay además un agujero que se descubrió al mirar el código: la dirección de
delivery que el cajero teclea en el PDV **se perdía**. Vivía solo en el
borrador del navegador (`frontend/app/pdv/tipos.ts`) y `venta` no tenía
ninguna columna que la recibiera — `referencia_atencion` es "para quién es el
pedido" (50 caracteres, "Carlos", "Rappi #1042"), no adónde va.

## Decisión

### Una dirección son dos cosas: el texto y su ancla

El texto se queda donde estaba. Se le suma un ancla, en cinco columnas que
llegan por un mixin (`core/model_base.UbicacionMixin`):

| Columna | Para qué |
|---|---|
| `ubicacion_place_id` | Identificador estable del lugar en Google. Es lo que se compara para saber si dos pedidos van al mismo sitio. |
| `ubicacion_lat` / `ubicacion_lng` | `Numeric(9,6)` — 6 decimales son ~11 cm, de sobra para una puerta. |
| `ubicacion_plus_code` | Se guarda aunque sea derivable de las coordenadas: viene gratis en la respuesta y derivarlo pediría una dependencia. |
| `ubicacion_distrito` | Lo que decide si un reparto cae en zona restringida (ADR-054), sin traer geometría ni PostGIS al proyecto. |

Prefijo `ubicacion_` y no `direccion_` porque la columna de texto no se llama
igual en las seis tablas.

**Todo nullable, y una dirección escrita a mano sigue siendo válida.** En
Tarapoto hay calles que Google no conoce. Exigir coordenadas sería no poder
dar de alta un proveedor porque un tercero no contestó — el mismo criterio de
ADR-005 y ADR-041.

### El pin no sobrevive a un cambio de texto

Corregir "Jr. Lima 200" por "Jr. Lima 400" tecleando, sin volver a elegir en
el mapa, **borra el ancla**. Si el texto dijera una calle y las coordenadas
otra, el reparto iría al lugar equivocado y cobraría la distancia equivocada.
Ante la duda se pierde el pin —que se vuelve a poner en dos clicks— y no la
verdad.

La regla vive en `shared/ubicacion.desanclar_si_cambio_el_texto` y la aplican
los cinco `editar_*`. El frontend hace lo mismo al vuelo, pero el que manda es
el servidor: la versión del navegador es cortesía visual.

No alcanzaba con la convención de PATCH de este ERP (`None` = no tocar):
justamente por esa convención, un formulario que corrige el texto sin ancla
nueva **no puede** pedir el borrado.

### El autocompletado y el mapa los habla el navegador

El SDK de Maps se carga en el cliente con una clave restringida por referente
HTTP, y es el navegador el que le pregunta a Google.

Se evaluó ponerlo detrás de un adaptador en `src/shared/integrations/`, que es
lo que manda CLAUDE.md para toda integración externa. Se descartó por dos
razones concretas:

1. **Los tokens de sesión de Places.** El elemento oficial
   (`PlaceAutocompleteElement`) los maneja solo, y son lo que hace que una
   búsqueda entera se cobre como una y no como ocho. Proxiarlo desde el
   backend obligaría a implementarlos a mano y a pagar por request.
   (ADR-072 deja de usar el elemento oficial y los maneja a mano — pero
   siempre en el cliente, nunca proxiados: la razón para no proxiar sigue
   valiendo igual, solo cambió quién abre y cierra la sesión.)
2. **El mapa interactivo con pin arrastrable no tiene versión server-side.**

La excepción es acotada y tiene su contrapeso: **lo que define plata sí vive
en el servidor** (ADR-054), con una segunda clave restringida por IP.

Consecuencia asumida: **la CSP se abre**. `connect-src` deja de ser `'self'`
puro y se suman los hosts de Google en `script-src`, `img-src`, `font-src`,
`style-src` y `worker-src`. La lista sale de la guía oficial de Google
recortada a lo que este ERP usa: **sin Street View y sin `'unsafe-eval'`**,
que Google recomienda por las dudas. Si algún día un mapa muere con un error
de `eval` en consola, esa es la línea que falta y la decisión hay que volver a
tomarla a conciencia.

### Dos cajas, no una

> **Superada por ADR-072** (2026-08-27). En la práctica, con dos cajas
> visibles se tecleaba en cualquiera de las dos indistintamente, y solo una
> de ellas dejaba algo anclado — la causa de que las direcciones de cliente
> se guardaran sin pin. ADR-072 vuelve a un solo `<input>`, que ahora busca
> él mismo y muestra sus sugerencias en un desplegable propio, sin perder la
> salida de texto libre que esta sección sí seguía protegiendo. Queda acá
> como registro de la decisión original.

El campo (`components/direccion/campo-direccion.tsx`) dibuja el buscador de
Google **arriba** del `<input>` de siempre, no en lugar de él:

- El buscador busca. Aparece solo si el SDK cargó.
- El `<input>` guarda, y se puede corregir a mano.

Es el mismo patrón que `BuscarDocumento`, que es un botón aparte de los campos
que rellena. Meter las dos funciones en un solo control obliga a elegir entre
"solo direcciones que Google conozca" y "sin autocompletado".

### La clave baja por contexto, no por props ni por `NEXT_PUBLIC_*`

La lee el proceso de Next y el layout la pasa una vez
(`components/direccion/config-mapas`). Pasarla como prop obligaría a tocar las
seis páginas **y** sus seis componentes cliente, y la séptima pantalla se
olvidaría.

No es `NEXT_PUBLIC_*` porque esa familia se hornea en el build — la misma
razón por la que se eliminó `NEXT_PUBLIC_API_URL`
(`docs/engineering/devops.md`). Así la clave se cambia reiniciando el
contenedor y no reconstruyendo la imagen.

### Las coordenadas de una persona son datos personales

`anonimizar_persona` borra el ancla junto con el domicilio. Un punto en el
mapa no admite la ambigüedad de un "por el mercado": es más identificatorio
que el texto, no menos. Sin esto la anonimización dejaba la puerta exacta en
la base (Ley 29733, ADR-011).

## Alternativas descartadas

- **Proxiar Places desde el backend.** Más caro (sin tokens de sesión) y más
  código, para no abrir la CSP. Se prefirió abrir la CSP a una lista acotada.
- **Solo autocompletado, sin mapa.** Evitaba la mitad de la apertura de CSP,
  pero deja sin corregir el caso más común en una ciudad con numeración
  irregular: Google pone el punto a media cuadra.
- **Polígonos y PostGIS.** Resolvería zonas de cobertura de verdad. Es mucha
  máquina para una lista de cuatro distritos; queda en la deuda del ROADMAP.
- **Una sola clave de Google.** Imposible: no se puede restringir la misma
  clave por referente HTTP y por IP a la vez.
- **Guardar la dirección como JSON.** Un `jsonb` evita cinco columnas por
  tabla y hace imposible indexar el distrito o filtrar por él sin funciones.

## Consecuencias

- Seis tablas con cinco columnas nuevas, todas nullable. Los registros que ya
  existen quedan sin ancla hasta que alguien edite la ficha; no hay backfill
  (un geocode masivo se cobra por registro).
- La CSP tiene hosts de terceros por primera vez.
- Sin `GOOGLE_MAPS_BROWSER_KEY` el ERP se comporta **exactamente** como antes
  de este cambio. Es lo que verifica `frontend/uso/direccion.spec.ts`, que
  corre sin clave a propósito.
- El delivery del PDV por fin guarda adónde fue.
