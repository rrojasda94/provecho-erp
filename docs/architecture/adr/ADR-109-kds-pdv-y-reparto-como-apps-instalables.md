# ADR-109 — KDS, PDV y Mi reparto como tres apps instalables

Fecha: 2026-09-23
Estado: aceptada

## Contexto

El personal opera tres pantallas desde teléfonos y tablets Android: la
cocina (`/kds`), la caja (`/pdv`) y el repartidor (`/reparto`). Se pidió
poder "descargarlas" como apps separadas, cada una con su ícono, entrando
con el mismo usuario y PIN del ERP.

`/reparto` ya era instalable (ADR-098) pero su manifest no tenía `id`;
`/kds` y `/pdv` no tenían manifest. Y había dos problemas que una app
instalada hace visibles:

1. **El login estaba fuera de la app.** Sin sesión, las tres pantallas
   mandaban a `/login`. Android abre lo que cae fuera del `scope` del
   manifest con barra de navegador, y al entrar el login mandaba al home del
   ERP (`/`), no de vuelta a la app. Desde un ícono "Cocina" se terminaba en
   el grid de módulos.
2. **La sesión muere al cerrar** (ADR-084), y Android cierra la app cuando
   necesita memoria. El repartidor tecleaba su usuario cada vez.

## Decisión

1. **Una app por pantalla, separadas por `scope`.** Tres manifests en
   `frontend/public/{kds,pdv,reparto}/manifest.webmanifest`, cada uno con
   `id`, `start_url` y `scope` iguales a su ruta, ícono y color propios.
   Mismo dominio; Android las instala y lista como tres apps. KDS y PDV con
   `orientation: any` (tablet); reparto sigue `portrait`.
2. **Cada app tiene su propio ingreso**, `/<app>/ingresar`: un `rewrite` de
   `next.config.mjs` a la misma página `/login`. La URL queda dentro del
   scope y no aparece la barra. El guard (`obtenerSesion(ingreso)`), los
   401 de cada página, el aviso de sesión expirada y "Cambiar de usuario"
   del PDV mandan ahí, con `?next=` a la pantalla exacta (el KDS conserva
   `?pantalla=`). Todo en `frontend/lib/ingreso.ts`.
3. **`next` se valida por regex exacta**: `/oauth/authorize` (ADR-083) o
   `/kds`, `/pdv`, `/reparto` con consulta opcional. Nada más, por el mismo
   motivo de siempre — `next` sale de la URL y sería un open redirect.
   `logoutAction(app)` recibe la app del cliente y la valida contra la lista.
4. **La app instalada recuerda el usuario, no la sesión.** En
   `display-mode: standalone`, el login guarda el último usuario en
   `localStorage` y al abrir solo falta el PIN; "No soy X" lo olvida. El PIN
   nunca se guarda (ADR-050) y en el navegador normal no se recuerda nada.
   ADR-084 queda intacto.
5. **Sin service worker.** Chrome Android ya no lo exige para instalar, la
   CSP (`worker-src blob:`) lo bloquearía, y el offline del PDV va por el
   hub de sucursal (ADR-009), no por el navegador.

## Alternativas descartadas

- **Sesión persistente (8 h) en las apps instaladas.** Menos PIN, pero una
  tablet de cocina o caja la levanta cualquiera y quedaría entrando como el
  turno anterior — justo lo que ADR-050 y ADR-084 cierran.
- **Un solo manifest con `scope: /`** y los tres módulos como accesos
  directos (`shortcuts`): una sola app, no tres íconos; no era lo pedido.
- **App nativa / TWA en Play Store.** Firma, cuenta de desarrollador y un
  ciclo de publicación para envolver las mismas tres páginas.

## Consecuencias

- Instalar: abrir `https://staging.majambo.com.pe/kds` (o `/pdv`,
  `/reparto`) en Chrome Android, entrar, y menú ⋮ → "Instalar app". El
  login (`/<app>/ingresar`) no lleva manifest: se instala desde la pantalla
  ya con sesión.
- Una app nueva instalable suma su manifest, su ruta al rewrite, a
  `SIGUIENTE_PERMITIDO` y a `APPS_INSTALABLES` en `lib/ingreso.ts`.
- En una tablet compartida, el usuario recordado es el del último que
  entró: se ve en pantalla y "No soy X" lo cambia.
