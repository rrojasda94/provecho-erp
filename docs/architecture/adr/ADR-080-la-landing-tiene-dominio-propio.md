# ADR-080 — La landing pública tiene dominio propio, y el proxy es quien lo acota

- Estado: aceptado
- Fecha: 2026-08-27
- Contexto: despliegue (staging), landing pública `reconocerte`
- Relacionado: ADR-060 (desplegar desde GitHub), ADR-061 (el cupón de la landing
  vive en `sales`), ADR-053 (la dirección se elige en el mapa), ADR-068 (la
  tarifa la fija Gerencia — la degradación silenciosa),
  `docs/engineering/staging.md`

## Contexto

ADR-061 dejó la landing del QR viva en `staging.majambo.com.pe/reconocerte`.
Esa URL no se puede imprimir en una mesa: dice «staging», es larga, y su raíz
es el ERP entero — `/login`, `/gerencia`, `/pdv`. El QR de una promoción no
puede llevar a un dominio que anuncia que es un entorno de prueba ni ofrecer,
a un clic de distancia, la pantalla de login del back office.

Se quiere `clientes.majambo.com.pe`, apuntando al mismo droplet.

## Decisión

### 1. El recorte va en Caddy, no en `middleware.ts`

Un bloque nuevo en el `Caddyfile` deja pasar `/reconocerte*`, `/_next/static/*`,
`/_next/image*`, `/marcas/*` y `/favicon.ico`; todo lo demás —incluida la
raíz— redirige 302 a `/reconocerte`.

La alternativa era un guard por host en `frontend/middleware.ts`, y tiene un
agujero concreto: el `matcher` de ese middleware lleva
`missing: [next-router-prefetch, purpose=prefetch]`, o sea que **no corre**
para las peticiones que traen esas cabeceras. Un guard ahí lo saltearía
cualquiera mandando `Next-Router-Prefetch: 1` a mano. Taparlo obligaba a
quitar ese `missing`, que existe para no calcular una CSP con nonce en cada
prefetch — deshacer una optimización deliberada para resolver algo que el
proxy ya resuelve, sin imagen nueva ni release.

Lo que el proxy no tiene es cobertura de CI: ningún test mira la forma del
`Caddyfile`. Por eso `caddy validate` y `caddy adapt` son pasos del runbook y
no una sugerencia (`docs/engineering/staging.md`).

### 2. `redir`, y no 404 ni `rewrite`

- Un **404** deja la raíz muerta, y la raíz es justo lo que alguien teclea al
  ver el QR. El 404 de Caddy además es una pantalla en blanco en inglés, y
  `not-found.tsx` está escrito para un empleado que tiene módulos a los que
  volver.
- Un **`rewrite`** serviría la landing bajo `/login`, con la URL mintiendo y su
  Server Action posteando a una ruta que no es la suya.
- **302 y no 301**: un 301 se cachea en el navegador para siempre. El día que
  este dominio tenga que servir otra cosa habría que pelear con la caché de
  cada teléfono que lo abrió.

Dos trampas de sintaxis quedaron documentadas en el propio archivo porque las
dos producen configuraciones **válidas** que hacen lo que no es:

- `redir /reconocerte 302` sin el `*` delante se lee como
  `redir <matcher> <destino>`: emite `Location: 302` y solo sobre la ruta que
  justamente no hay que redirigir. Va `redir * /reconocerte 302`.
- Invertir los dos `handle` redirige `/reconocerte` a sí mismo
  (`ERR_TOO_MANY_REDIRECTS`).

### 3. `/_next/static/*` entra entero, y eso publica los chunks del back office

Hay **un solo proceso de Next** para los dos dominios, así que los chunks
compartidos son los mismos. Recortar por ruta ahí no se puede sin partir la
aplicación en dos builds.

Consecuencia aceptada: desde el dominio público se pueden bajar los chunks de
`/_next/static/chunks/app/(app)/gerencia/…`. Eso revela **estructura de rutas,
no datos** — la API sigue exigiendo su JWT. La alternativa (un segundo servicio
`web` con su propio build) cuesta una imagen, un contenedor y un pipeline para
esconder nombres de archivo.

Y no es negociable en el otro sentido: **omitir `/_next/static/*` es peor que
no hacer nada**. La página se pinta igual —viene del servidor— y nunca hidrata,
porque `nosniff` rechaza el HTML del redirect donde el navegador esperaba
JavaScript. Se ve perfecta y no funciona ningún campo.

### 4. Esto no es un control de seguridad

`staging.majambo.com.pe/login` sigue exactamente igual de público. Lo que
protege al back office es el login, no el nombre del host. Este ADR compra una
URL limpia para un QR y nada más; leerlo como «el ERP quedó oculto» sería
justo el error que conviene no cometer.

Se agrega `X-Robots-Tag: noindex, nofollow` al dominio nuevo: es un formulario
que pide DNI y teléfono, sobre datos desechables, y no tiene por qué ser un
resultado de búsqueda.

## Consecuencias

- **Dos URLs para la misma landing.** La vieja no se apaga; el QR usa la nueva,
  con `https://` explícito.
- **Un solo `web` para los dos hosts**, así que nada se puede configurar por
  dominio (ni el Map ID, ni la CSP, ni las cabeceras de `next.config.mjs`).
- **El `Caddyfile` del repo no lo despliega nadie.** `desplegar.yml` hace `scp`
  de `scripts/desplegar.sh` y de nada más; este archivo y el compose se copiaron
  a mano el 2026-08-23. Mergear este cambio **no toca el droplet** hasta que
  alguien lo copie. El procedimiento —con respaldo y `caddy validate` antes del
  `reload`— queda en `staging.md`, y automatizarlo va a `deuda/ci-cd.md`
  emparejado con el `dynamic a` que ya estaba anotado: los dos necesitan la
  misma maquinaria, y un `Caddyfile` inválido deja staging **sin proxy**, que
  es peor que el 502 que ese archivo ya advierte.
- **Los datos son desechables y las personas no.** Esto corre sobre el Postgres
  de staging, declarado descartable. Los DNI, teléfonos y fechas de nacimiento
  que entren por ahí son de gente real, se consultan contra RENIEC con el token
  de QA de Factiliza y quedan en una base con `pg_dump` a 30 días y sin la
  custodia que ADR-011 supone. Aceptado **como prueba**, no como padrón: lo que
  se junte no se conserva. Anotado en
  `deuda/proteccion-de-datos-personales.md`; la pregunta de fondo —si un QR
  impreso puede apuntar a staging— sigue abierta.
- Si algún día se mete un CDN o un segundo proxy delante que reescriba `Host`,
  **todos los registros fallan** con «Invalid Server Actions request» y solo
  eso: Next compara `Origin` contra `X-Forwarded-Host`, que hoy Caddy manda
  bien.

## Lo que apareció construyendo esto

El campo de dirección **nunca había funcionado en ninguna pantalla**, y no por
falta de clave. `cargarMaps` resolvía en cuanto existía `window.google.maps`,
pero ese objeto aparece **antes** de que el bootstrap de `loading=async` defina
`importLibrary`. El llamador recibía un namespace a medio armar y moría con
«maps.importLibrary is not a function» — dentro del `.catch()` mudo de
`CampoDireccion`, o sea sin ningún síntoma salvo un campo de texto pelado,
idéntico a no tener clave configurada.

Esta rama y ADR-072 dieron con el mismo bug el mismo día, en paralelo. El
arreglo de fondo salió por ADR-072 en la 0.8.1; acá quedan las dos piezas que
allá faltaban:

- **El sondeo ya no cuelga del evento `load`.** Un `<script>` que ya terminó de
  cargar no vuelve a emitirlo, y la promesa memoizada es del módulo: en cada
  recarga en caliente se reusaba el `<script>` viejo y la espera no terminaba
  nunca. Ahora se sondea de una; `error` sigue cortando.
- **El `catch` deja de ser mudo.** Es la misma lección de ADR-068 §3 en su
  forma más cara: una degradación correcta de cara al cajero —una venta no se
  pierde porque un tercero no contestó— vuelve invisible un bug propio. Ahora
  escribe el motivo en consola, que es lo que habría convertido una sesión de
  diagnóstico en dos minutos.

Los dos en `lib/google-maps.ts` y `components/direccion/campo-direccion.tsx`,
con su prueba (`lib/google-maps.test.ts`).

## Alternativas descartadas

- **Una app de Next aparte para la landing.** Un build, una imagen, un servicio
  y un pipeline más para una página que ya existe y comparte diseño, layout y
  Server Actions con el resto.
- **Servir la landing desde el propio Caddy como estático.** Necesita las
  Server Actions y el render en servidor de la promoción activa (`force-dynamic`
  en `page.tsx`): sin proceso de Next no hay landing.
- **Reescribir el host en `next.config.mjs`.** No hay reescritura por host que
  se aplique antes del render sin middleware, y el middleware es el punto 1.
