# Historial — Módulo `storefront`

Estado vigente: 🔶 En curso — PR1 (2026-09-17, ADR-103): sitio público de
solo lectura para Charlie's Pizzas en `charlies.majambo.com.pe`, servido por
una app Next.js separada del ERP (`storefront/`). PR2 (2026-09-17, ADR-104):
cuentas de cliente (email/clave + Google), direcciones, favoritos y "tu
último pedido", con credencial separada de la del ERP. Carrito, checkout y
pagos (Izipay) quedan para PR3; Playwright del sitio y SEO (sitemap, OG)
para PR4. Ver `docs/roadmap/deuda/modulo-storefront.md`.

## Cronología

### 2026-09-17 — PR1: sitio público, CMS y fotos (ADR-103)

Encargo del usuario: una web de marca completa para Charlie's Pizzas
(catálogo con fotos e ingredientes, promos web, locales en mapa, cuentas
de cliente, pedidos con pago online, "Nosotros", "Trabaja con nosotros"),
insumos externos: brand guideline de Charlie's (`brand-voice-guidelines.md`,
`majambo.md` §3.1, `Brandbook_CharliesPizza.pdf`) y un prototipo de
storefront ya construido con Claude Design, portado a HTML/JS estándar.

Decisión de arquitectura central (ADR-103): el sitio vive en una **app Next
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

### 2026-09-17 — PR2: cuentas de cliente (ADR-104)

Sobre la rama de PR1, sin pausa (encargo del usuario: PRs encadenados,
"en automático uno tras otro"). Alcance: cuentas de cliente para el sitio
de Charlie's Pizzas, separadas de las credenciales del ERP.

- **Tablas nuevas en `storefront`**: `storefront_cuenta` (email único,
  `password_hash` Argon2id nullable, `google_sub` único nullable,
  `cliente_id` FK a `cliente`, `intentos_fallidos`, `bloqueado_hasta`),
  `storefront_direccion` (con `UbicacionMixin`, una predeterminada),
  `storefront_favorito` (única por cuenta+producto),
  `storefront_refresh_token` (rotación con detección de reuso, mismo
  patrón que `users`) — migración `a4f1a2f11b85`.
- **Aislamiento de credenciales (ADR-104)**: `security.py` propio del
  módulo, JWT firmado con `STOREFRONT_JWT_SECRET` (nunca `JWT_SECRET`) y
  `aud="storefront"`; el decoder exige esa audiencia, así que un token de
  cliente jamás decodifica en un endpoint del ERP y viceversa (probado en
  `test_token_de_cuenta_web_no_sirve_en_el_erp` /
  `test_token_del_erp_no_sirve_en_storefront`). Cookies propias del
  dominio (`charlies_token`, `charlies_refresh`), httpOnly, nunca las de
  `frontend/` (`provecho_token`).
- **Login con Google**: verificación server-side del `id_token` contra el
  JWKS de Google (`PyJWKClient` de PyJWT, sin dependencia nueva). Cuenta
  nueva por Google exige los mismos datos que el registro por email
  (RN-WEB-005: nombre, DNI, teléfono, cumpleaños, dirección) antes de
  poder operar — el frontend resuelve esto con un formulario de
  "completar datos" tras el primer intento fallido.
- **Vínculo a `cliente` por evento**: `storefront` publica
  `storefront.cuenta_registrada`; un listener de `sales` llama a
  `clientes.crear_o_encontrar_cliente` (RENIEC + fallback, idempotente
  por documento) y publica `sales.cliente_vinculado`, que un listener de
  `storefront` usa para completar `cuenta.cliente_id`. Si faltan datos
  para crear el cliente, el registro de la cuenta no se revierte — solo
  queda sin vincular.
- **Seguridad de cuenta**: bloqueo tras `MAX_INTENTOS_FALLIDOS = 5`
  (`DURACION_BLOQUEO = 15 min`); el commit del intento fallido/la
  revocación de sesión se hace **antes** de lanzar la excepción HTTP —
  de lo contrario el `rollback()` automático de `get_db()` deshace el
  contador (bug encontrado y corregido durante este PR, mismo patrón que
  `users/api/routers.py::login`).
- **Frontend `storefront/`**: `/cuenta/registro`, `/cuenta/ingresar`
  (con botón de Google), `/cuenta` (perfil, direcciones con alta/baja,
  favoritos, "tu último pedido"); header con enlace "Ingresar"/"Mi
  cuenta" según sesión; home muestra el último pedido o, si no hay,
  favoritos en vez de destacados genéricos; corazón de favorito en cada
  tarjeta de la carta (enlaza a login si no hay sesión).
- **ERP**: sin cambios de pantalla — PR2 es enteramente cuenta de
  cliente/API pública.

Verificado antes de abrir el PR: suite completa de `pytest` en verde
(2786 pasados, 3 saltados), `ruff check` limpio, `openapi.json`
regenerado, `npm run lint`/`typecheck`/`test`/`build` en verde en
`storefront/`.
