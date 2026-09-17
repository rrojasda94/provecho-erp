# Historial — Módulo `storefront`

Estado vigente: 🔶 En curso — PR1 implementado (2026-09-17, ADR-101): sitio
público de solo lectura para Charlie's Pizzas en `charlies.majambo.com.pe`,
servido por una app Next.js separada del ERP (`storefront/`). Cuentas de
cliente, direcciones/favoritos, carrito y checkout con pagos (Izipay) quedan
para PR2/PR3; Playwright del sitio y SEO (sitemap, OG) para PR4. Ver
`docs/roadmap/deuda/modulo-storefront.md`.

## Cronología

### 2026-09-17 — PR1: sitio público, CMS y fotos (ADR-101)

Encargo del usuario: una web de marca completa para Charlie's Pizzas
(catálogo con fotos e ingredientes, promos web, locales en mapa, cuentas
de cliente, pedidos con pago online, "Nosotros", "Trabaja con nosotros"),
insumos externos: brand guideline de Charlie's (`brand-voice-guidelines.md`,
`majambo.md` §3.1, `Brandbook_CharliesPizza.pdf`) y un prototipo de
storefront ya construido con Claude Design, portado a HTML/JS estándar.

Decisión de arquitectura central (ADR-101): el sitio vive en una **app Next
separada** (`storefront/`), no en una ruta más del proceso `web` compartido
con el ERP como hizo ADR-080 para la landing del QR — el sitio de marca
necesita SEO real, tema y CSP propios (paleta verde/crema del brandbook de
Charlie's, no la brasa/acero de Provecho), y una superficie de ataque menor
que la que ADR-080 aceptó para una landing de un solo formulario.

Alcance de PR1, entregado como slice único de solo lectura:

- **Módulo backend `storefront`**: `storefront_contenido` (CMS mínimo con
  6 claves fijas: hero, nosotros, contacto, trabaja, pie, seo), fotos de
  catálogo (presign a S3, reusa `shared.adjuntos`/`shared.integrations.
  storage.s3`, mismo patrón que `assets.documentos`), y la superficie
  pública `/api/v1/storefront/publico/*` (sin JWT, rate limit 120/h por IP,
  `Cache-Control: public, max-age=60`): contenido, carta, detalle de
  producto, ingrediente, sucursales, promociones con canal `web`,
  convocatorias publicadas. Todo lo público pasa por contratos
  `application/queries_publicas.py` de `sales`/`inventory`/`users`/`rrhh` —
  nunca importa su dominio ni infraestructura (RN-WEB-001).
- **Columnas nuevas**: `producto_comercial.descripcion`,
  `articulo.descripcion` (Text, nullable), `sucursal.telefono`
  (String(20), nullable) — migración `405c9227fce3`, escrita a mano
  (sin Postgres disponible para `alembic --autogenerate` en el entorno de
  build de este PR; revisar con `alembic check` antes de mergear).
- **App `storefront/`**: home (hero + promos web + destacados), carta con
  búsqueda en cliente (normalización + trigramas + coeficiente de Dice,
  cubre nombre mal escrito e ingrediente, sin dependencia nueva) y filtros
  (precio, tamaño, disponibilidad), ficha de producto con ingredientes
  clicables (`<dialog>` nativo con foto y descripción), mapa de locales
  (Google Maps JS, solo `marker`) con horario y "abierto ahora", Nosotros,
  Trabaja con nosotros (enlaza a `/postular/{token}` en
  `clientes.majambo.com.pe`, ADR-087). `lib/api.ts` nunca lanza por un
  fallo de red: el `next build` sin API arriba se prerrenderiza vacío en
  vez de romper.
- **ERP**: pantalla nueva `/web` (permiso `storefront.leer`/`.editar`,
  agregado al rol `marketing`) para editar el contenido y las fotos;
  `sucursales-cliente.tsx` gana teléfono y un editor de horario de un
  tramo por día; `promociones-cliente.tsx` gana el checkbox de canal
  `web`.
- **Infra**: tercera imagen Docker (`provecho-erp-charlies`), contenedor
  `charlies` en `docker-compose.yml`/`docker-compose.staging.yml`, bloque
  propio en `Caddyfile` (sin `X-Robots-Tag: noindex` — este sitio sí quiere
  indexarse), job `storefront` y build+healthcheck en `ci.yml`, tercera
  imagen en `release.yml`, `PROVECHO_CHARLIES_IMAGE` en
  `scripts/desplegar.sh`. Despliegue real a staging queda pendiente
  (`docs/engineering/staging.md` → Pendiente): falta el registro DNS y
  copiar los archivos actualizados al droplet.

Verificado antes de abrir el PR: suite completa de `pytest` en verde
(2758 pasados), `ruff check` limpio, `npm run lint`/`typecheck`/`test`/
`build` en verde en `frontend/` y en `storefront/` (sin API arriba para el
build), `openapi.json` regenerado.
