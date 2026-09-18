# `storefront` — Sitio público de Charlie's Pizzas

App Next.js **aparte** de `frontend/` (ADR-103): sirve
`charlies.majambo.com.pe`. No comparte proceso, tema, CSP ni build con el
ERP — el único punto de contacto es la API, y solo con
`/api/v1/storefront/publico/*` (sin JWT, backend `src/modules/storefront/`).

## Alcance de este slice (PR1)

Sitio de solo lectura: home con promos web y destacados, carta con
búsqueda (nombre, mal escrito, ingrediente) y filtros (precio, tamaño,
disponibilidad), ficha de producto con ingredientes clicables (diálogo con
foto y descripción), mapa de locales con horario y "abierto ahora",
"Nosotros" y "Trabaja con nosotros" (enlaza a `/postular/{token}` en
`clientes.majambo.com.pe`, ADR-087). El contenido y las fotos se editan en
el ERP, módulo "Sitio web" (`frontend/app/(app)/web/`).

Sin cuentas de cliente, carrito ni pagos — eso es PR2/PR3.

## Cómo correr

```bash
cd storefront
npm ci
API_INTERNAL_URL=http://localhost:8000 npm run dev
```

Necesita `STOREFRONT_MARCA_ID` configurado en la API (`.env` del backend)
para que los endpoints públicos respondan algo — sin marca configurada,
todo devuelve 404 ("sitio no configurado").

## Variables de entorno (proceso de Next)

- `API_INTERNAL_URL` — base de la API vista desde el servidor (nunca desde
  el navegador; no hay proxy genérico como en `frontend/`).
- `GOOGLE_MAPS_BROWSER_KEY`, `GOOGLE_MAPS_MAP_ID` — mapa de locales
  (`app/locales/`). Sin clave, el mapa muestra un mensaje y la lista de
  locales sigue funcionando igual.
- `STOREFRONT_IMAGENES_HOST` — host permitido para `next/image` (bucket S3
  de fotos de catálogo).
- `NEXT_PUBLIC_SITE_URL` — base pública para `sitemap.ts`, Open Graph y
  JSON-LD (ADR-105/PR4). Vacío ⇒ cae a `https://charlies.majambo.com.pe`,
  el dominio de producción.

## Pruebas

```bash
npm test        # lib/*.test.ts (búsqueda), node --test
npm run lint
npm run typecheck
npm run build
```

### Playwright (`e2e/`)

```bash
npm run test:e2e
```

Un solo recorrido (ADR-047, mismo criterio que la suite `e2e` del ERP: "el
flujo del dinero funciona de punta a punta", nada más): carrito → checkout de
invitado → recojo en efectivo → confirmación con número de pedido. Levanta su
propia API (SQLite desechable, `storefront/e2e.db`) y su propio Next, en el
rango de puertos 8110/3110 (no 8100/3100, que ya usa la suite del ERP —
`docs/engineering/trabajo-en-paralelo.md`).

- `PYTHON` — mismo requisito que el resto del repo (`docs/engineering/`):
  cada worktree comparte el `.venv` de la raíz del checkout principal, sin
  uno propio; si el `python` del PATH no tiene `fastapi`/`sqlalchemy`
  instalados, fijar `PYTHON` a esa ruta explícita.
- **Redis debe estar arriba** (`docker compose up -d redis` alcanza, no hace
  falta el resto del stack): confirmar un pedido dispara el listener de
  `sales` hacia el asiento contable y el barrido de Celery, y encolar una
  tarea sin Redis reintenta contra el backend de resultados durante ~20 s
  antes de rendirse — el checkout responde, pero mucho más lento de lo que
  cualquier timeout de Playwright tolera.
- `e2e/preparar-bd.mjs` reseedea la base **y borra `storefront/.next`
  entero** antes de cada corrida: no alcanza con vaciar `.next/cache` —si
  queda una build de producción vieja (`npm run build` de una verificación
  anterior), `next dev` arranca en caliente con ese HTML/RSC ya
  prerenderizado, de un `marca_id`/`producto_id` que ya no existe en la base
  recién sembrada.
