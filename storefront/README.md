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

## Pruebas

```bash
npm test        # lib/*.test.ts (búsqueda), node --test
npm run lint
npm run typecheck
npm run build
```

Playwright de este sitio queda para PR4 (hardening).
