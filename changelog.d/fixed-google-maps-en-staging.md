- **El campo de dirección nunca pudo mostrar el mapa** (2026-08-25, ADR-053).
  Un bloqueo mutuo en `components/direccion/campo-direccion.tsx`: el
  contenedor del buscador se renderizaba solo con `conMapa` en `true`, y el
  efecto que pone `conMapa` en `true` necesitaba ese contenedor para montar el
  `PlaceAutocompleteElement` — salía antes por su `if (!buscadorRef.current)
  return`. El estado que habilita el contenedor dependía del contenedor. Con
  clave o sin ella, el resultado era el mismo: «El mapa no está disponible».
  La integración estuvo muerta desde que se escribió.

  Se descubrió encendiendo la clave en staging, y costó descartar tres
  hipótesis antes —variable que no llegaba al contenedor, Turbopack inlineando
  `process.env` en el build, restricciones mal puestas en la consola de
  Google— porque el `.catch` del efecto tiene un «silencio deliberado» y por
  ahí no salía ninguna excepción: salía un `return` limpio. En el navegador de
  staging el SDK cargaba, `window.google` existía e `importLibrary("places")`
  respondía; todo estaba bien menos el orden de dos líneas de JSX.

  Ahora los dos contenedores se renderizan siempre y se ocultan con CSS, que
  es lo que ya hacía el del mapa por dentro (`visible ? "h-44" : "hidden"`).

  **Nadie podía verlo**: `frontend/uso/direccion.spec.ts` corre **sin** clave
  a propósito —eso sigue siendo correcto y valioso— pero era la única prueba
  que tocaba el campo, y sin clave este camino ni se ejecuta. Se suma
  `frontend/uso/direccion-con-mapa.spec.ts`, el gemelo con el mapa encendido:
  el SDK lo responde Playwright interceptando `maps.googleapis.com`, así que
  no gasta cuota de un proveedor pago ni sale a la red desde CI. De yapa cubre
  la CSP — la respuesta llega desde ese host, así que sacarlo de
  `middleware.ts` pone la prueba en rojo.

- **La clave de Google Maps no llegaba al frontend en staging** (2026-08-25).
  El servicio `web` no tiene `env_file: .env` —es a propósito, así nunca ve
  `GOOGLE_MAPS_SERVER_KEY`, la que define cuánta plata paga el cliente— y
  recibe solo lo que su `environment:` declara. `docker-compose.yml` declaraba
  las tres variables del mapa; `docker-compose.staging.yml` y
  `docker-compose.prod.yml` no. Resultado: la clave puesta en el `.env` del
  servidor y el mapa apagado, sin un solo error en consola ni en los logs. Se
  comprueba en un comando (`docker compose exec web env | grep GOOGLE`), que
  ahora es el paso 0 de la verificación en `integraciones-google.md`.
- **`.env.staging.example` documentaba `GOOGLE_API_KEY`**, un nombre renombrado
  hace dos meses a `GOOGLE_MAPS_BROWSER_KEY` y que `Settings` descarta en
  silencio (`extra="ignore"`), mientras faltaban las seis variables reales de
  Google. `tests/test_settings.py` ahora prueba también el sentido inverso —que
  toda variable del ejemplo de staging la lea alguien—, que es exactamente lo
  que dejó pasar esto durante dos meses.
- **El workflow *Desplegar* copiaba solo `scripts/desplegar.sh`.**
  `docker-compose.staging.yml` y el `Caddyfile` se habían copiado a mano al
  montar el servidor y nadie los volvía a sincronizar, así que el arreglo de
  arriba no habría llegado nunca al droplet. Ahora los tres viajan en cada
  despliegue, precedidos de un paso que deja el `diff` contra lo que hay en el
  servidor en el resumen del run: el compose de allá lleva ediciones a mano y
  hay que ver qué se pisa antes de pisarlo. Es el mismo criterio que ADR-060 ya
  había aplicado al script — el compose se le había escapado.
- **`NEXT_PUBLIC_API_URL` sobrevivía en el compose de staging** sin que una sola
  línea del frontend la leyera, y siendo `NEXT_PUBLIC_*` se hornea en el build:
  no podía funcionar en tiempo de ejecución ni queriendo. Eliminada.
