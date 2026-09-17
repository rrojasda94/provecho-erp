# ADR-103 — El sitio de marca es un módulo `storefront` y una app Next aparte

Fecha: 2026-09-17
Estado: aceptada

## Contexto

Grupo Majambo quiere una web pública de Charlie's Pizzas
(`charlies.majambo.com.pe`): carta con fotos e ingredientes, promos
exclusivas de canal web, mapa de locales, "Nosotros", "Trabaja con
nosotros" y, en fases siguientes, cuentas de cliente y pedidos con pago
online. Tiene que verse y sentirse como la marca —paleta verde/crema del
brandbook de Charlie's, no el acero/brasa de Provecho— y no puede filtrar
nada de lo que `majambo.md` §3.1.12 marca como privado 🔒 (números del
equipo, datos de otros clientes, recetas, costos, credenciales).

ADR-080 ya resolvió un caso parecido —la landing `clientes.majambo.com.pe`—
con la decisión contraria: **un solo proceso Next** para todos los dominios,
recortado por Caddy. Esa decisión fue correcta para una landing de un solo
formulario que comparte diseño y Server Actions con el resto. No lo es acá:

- **SEO real.** La landing lleva `X-Robots-Tag: noindex, nofollow` a
  propósito —es un formulario desechable—; el sitio de marca necesita lo
  contrario (indexarse, tener sitemap, OG tags).
- **Tema propio.** ADR-080 §"Consecuencias" ya lo advierte: *"un solo `web`
  para los dos hosts, así que nada se puede configurar por dominio (ni el
  Map ID, ni la CSP, ni las cabeceras de `next.config.mjs`)"*. El sitio de
  marca necesita su propia paleta, tipografía y CSP, no las de Provecho.
- **Superficie de ataque.** Compartir proceso con el back office significa
  que los chunks de `/gerencia`, `/pdv`, `/contabilidad` son descargables
  desde el dominio público (ADR-080 §3 ya lo acepta como costo para la
  landing: *"estructura de rutas, no datos"*). Para un sitio de e-commerce
  con cuentas de cliente y pagos, ese costo ya no es aceptable: cuanto menos
  superficie del ERP quede alcanzable desde un dominio público, mejor.
- **Aislamiento de credenciales.** El plan de negocio exige que las cuentas
  de cliente web sean completamente independientes de las credenciales del
  ERP (PR2). Un solo proceso Next con un solo conjunto de cookies/CSP hace
  ese aislamiento más difícil de razonar y de probar que dos apps
  separadas con sus propios dominios de cookie.

## Decisión

**Segunda app Next.js**, `storefront/` en la raíz del monorepo (hermana de
`frontend/`), con su propio `package.json`, `Dockerfile`, imagen de
contenedor (`provecho-erp-charlies`) y bloque `Caddyfile` propio:

```
charlies.majambo.com.pe {
    reverse_proxy charlies:3000
}
```

Reglas de aislamiento (para que esta segunda app no reabra el problema que
ADR-080 evitó compartiendo proceso):

1. **`storefront` (el proceso Next) solo conoce `API_INTERNAL_URL`** y solo
   llama a `/api/v1/storefront/publico/*` (y, desde PR2, a
   `/api/v1/storefront/cuentas/*`). No hay proxy genérico como
   `frontend/app/api/proxy/[...ruta]`: el navegador nunca habla con la API
   directo (`connect-src 'self'`), y el servidor Next solo puede pedir lo
   que el módulo `storefront` decidió exponer.
2. **Superficie pública = allowlist de DTOs.** Cada `*PublicoOut` en
   `src/modules/storefront/api/schemas.py` enumera sus campos; nunca se
   serializa un modelo ORM ni un dict con `**` desde otro módulo. Ver
   RN-WEB-001.
3. **`storefront` (el módulo backend) entra a los demás módulos SOLO por su
   `application/queries_publicas.py`** (regla ya vigente de
   `tests/test_arquitectura.py`), igual que cualquier módulo.
4. **Credenciales separadas** (desarrollado en detalle en PR2/ADR-102): JWT
   de cuenta web con secreto y `aud` propios; cookies con nombre y dominio
   propios; el decoder del ERP y el del storefront se rechazan mutuamente.

## Consecuencias

- **Costo aceptado**: una tercera imagen Docker, un tercer job de CI, un
  tercer bloque de Caddy, un `next build` más. Es exactamente lo que
  ADR-080 rechazó para la landing por no compensar ("una imagen, un
  contenedor y un pipeline para una página que ya existía") — acá sí
  compensa porque el sitio de marca es un producto propio con SEO, tema y
  seguridad que la landing nunca necesitó.
- ADR-080 sigue vigente para `clientes.majambo.com.pe`: la landing del QR,
  el seguimiento de delivery y la postulación siguen viviendo en el proceso
  `web` compartido con el ERP. Este ADR no las mueve.
- Un cambio de tema, CSP o cabecera del sitio de marca no toca
  `frontend/next.config.mjs` ni el `middleware.ts` del ERP, y viceversa.
- El registro DNS de `charlies.majambo.com.pe` y el `Caddyfile` del droplet
  se gestionan igual que en ADR-080: el archivo del repo no se despliega
  solo (`docs/engineering/staging.md`), y el registro A tiene que existir
  antes de agregar el bloque (Let's Encrypt corta tras 5 fallos por hora).
- La clave del navegador de Google Maps (`GOOGLE_MAPS_BROWSER_KEY`) es
  compartida entre `web` y `charlies` —mismo proyecto de Google Cloud—, pero
  su lista de referrers HTTP debe incluir el nuevo dominio
  (`docs/engineering/integraciones-google.md`).

## Alternativas descartadas

- **Ruta `(publico)/charlies` en el proceso `web` existente**, como
  `reconocerte`. Descartada por las tres razones de "Contexto": SEO, tema y
  superficie de ataque. Es el camino de menor costo pero reabre exactamente
  lo que ADR-080 §"Consecuencias" ya señaló como su límite.
- **Servir el sitio como HTML estático detrás de Caddy.** No sirve: la carta
  y las sucursales cambian en el ERP y el sitio necesita revalidación
  (`revalidate = 60`), no un build por cada cambio de precio.
