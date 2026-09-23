# `storefront` — Sitio web público de marca

Dueño del contenido editable, las fotos de catálogo, las cuentas de cliente
web (desde PR2) y (desde PR3) los pedidos del sitio de marca
(`charlies.majambo.com.pe`, ADR-105). Es la única puerta por la que la app
`storefront/` (un proceso Next.js aparte, sin JWT de ERP) lee y escribe al ERP.

## Alcance de PR1 (sitio público de solo lectura)

- **CMS mínimo** (`storefront_contenido`): textos editables por marca —hero,
  nosotros, contacto, trabaja, pie, seo— con claves fijas (`domain.rules`).
- **Fotos de catálogo**: subida presignada a S3 para fotos de `producto_comercial`
  e `insumo` (artículo), reusando `src.shared.adjuntos`/`src.shared.integrations.storage.s3`.
- **Superficie pública de solo lectura** (`api/publico_routers.py`, sin JWT,
  con rate limit por IP): contenido, carta con precio/ingredientes/foto,
  sucursales activas de la marca, promociones con canal `web`, convocatorias
  publicadas.

## Alcance de PR2 (cuentas de cliente, ADR-104)

- **Cuenta de cliente web** (`storefront_cuenta`): registro por email/clave
  o Google, login, refresh rotativo con detección de reuso, logout, perfil.
  Credencial **completamente separada** del `usuario` del ERP — secreto de
  JWT, `aud` y tabla de refresh token propios (`infrastructure/security.py`,
  nunca importa `users.infrastructure.security`).
- **Direcciones** (`storefront_direccion`) y **favoritos**
  (`storefront_favorito`) de la cuenta.
- **Enlace a `cliente`** por evento (`storefront.cuenta_registrada` →
  `sales.cliente_vinculado`, ver ADR-104 y `docs/architecture/events.md`) —
  `storefront` nunca importa `sales.application.clientes`.
- **"Tu último pedido"**: `GET /storefront/cuentas/me/ultimo-pedido` lee
  `sales.queries_publicas.ultimo_pedido_de_cliente` (cualquier canal, no
  solo web — ese canal todavía no existe, llega en PR3).

Este PR no publica ni consume eventos del lado de contenido/fotos (sigue
igual que PR1); el módulo SÍ gana `application/listeners.py` para el enlace
a `cliente`. PR3 agrega pedidos (`storefront.pedido_web_confirmado`).

## Regla de oro (RN-WEB-001)

La superficie pública **nunca** devuelve: `empresa_id`/`grupo_id`, costos,
datos de `persona` (DNI, teléfono, dirección de terceros), remuneración,
usuarios/proveedores, cantidades de receta. Solo los campos enumerados en
cada `*PublicoOut`/`*Out` de `api/schemas.py`, `api/cuentas_schemas.py` y
`api/pedidos_schemas.py`. Ver `docs/domain/business-rules.md` RN-WEB-001..015.

## Dependencias (contrato público, nunca dominio ajeno)

- `sales.application.queries_publicas`: `carta_publica`, `marca_de_producto`,
  `promociones_web_vigentes`, `marca_publica`, `ultimo_pedido_de_cliente`,
  `carga_activa_por_sucursal`, `puntos_venta_web_de_sucursales`,
  `cotizar_delivery_publico` (los tres últimos, ADR-104/PR3: asignación
  automática de local y cotización de delivery del checkout).
- `inventory.application.queries_publicas`: `insumos_de_recetas`, `articulos_publicos`.
- `users.application.queries_publicas`: `sucursales_publicas_de_marca`, `empresas_de_marca`.
- `rrhh.application.queries_publicas`: `convocatorias_publicadas`.
- `users.infrastructure.models.Sucursal` (excepción cruzada global de
  `tests/test_arquitectura.py`, no un contrato propio): la asignación de
  local lee `estado`/`marca_id`/`ubicacion_*` directo, igual que cualquier
  otro módulo del ERP.

`sales` a su vez consume `storefront.pedido_web_confirmado` (ADR-105) —
ver `docs/architecture/events.md`.

## Endpoints

Gestión de contenido (JWT del ERP + `storefront.leer`/`storefront.editar`,
prefix `/api/v1/storefront`): `GET/PUT /contenido`,
`POST /fotos/{entidad}/{entidad_id}/presign-upload`,
`POST/GET/DELETE /fotos/{entidad}/{entidad_id}`.

Cuenta de cliente (sin JWT del ERP — trae el suyo propio, prefix
`/api/v1/storefront/cuentas`, rate limit por IP): `POST /registro`,
`/login`, `/google`, `/refresh`, `/logout`; `GET/PATCH /me`,
`GET /me/ultimo-pedido`; `GET/POST/PATCH/DELETE /me/direcciones[/{id}]`;
`GET/POST/DELETE /me/favoritos[/{producto_id}]` (JWT de cuenta en estos
últimos).

Públicos de solo lectura (sin JWT, prefix `/api/v1/storefront/publico`,
`rate_limit("storefront_publico", 120, 3600)`): `GET /contenido`, `/carta`,
`/productos/{id}`, `/ingredientes/{id}`, `/sucursales`, `/promociones`,
`/convocatorias`.

Checkout (sin JWT del ERP; JWT de cuenta **opcional** — invitado admitido,
RN-WEB-009; rate limit propio `rate_limit("storefront_pedidos", 20,
3600)` en la confirmación, ADR-105): `POST /publico/pedidos/cotizar`
(vista previa: sucursal, ETA, costo de delivery), `POST /publico/pedidos`
(confirma, crea la `Venta` por evento y devuelve el estado final —
síncrono en la práctica), `GET /publico/pedidos/{id}?token=...` (consulta
por el `token_acceso` que devolvió la confirmación, para un invitado sin
cuenta).

## Configuración

`STOREFRONT_MARCA_ID` (vacío ⇒ públicos responden 404 — "sitio no configurado"),
`STOREFRONT_SUCURSAL_ID` (vacío ⇒ primera sucursal activa de la marca),
`STOREFRONT_CANAL`/`STOREFRONT_MODALIDAD` (con qué lista de precios se resuelve
la carta pública — `web`/`delivery` por defecto desde PR3), `STOREFRONT_URL_POSTULAR_BASE`,
`STOREFRONT_JWT_SECRET`/`STOREFRONT_ACCESS_TOKEN_MINUTES`/
`STOREFRONT_REFRESH_TOKEN_DAYS` (credencial de cuenta, ADR-104 — el secreto
nunca debe coincidir con `JWT_SECRET`), `GOOGLE_OAUTH_CLIENT_ID` (vacío ⇒
"Continuar con Google" no se ofrece), `STOREFRONT_ETA_BASE_MINUTOS`/
`STOREFRONT_ETA_MINUTOS_POR_PEDIDO`/`STOREFRONT_SATURACION_PEDIDOS` (ETA y
asignación de local, ADR-105/104), `IZIPAY_API_KEY`/`IZIPAY_WEBHOOK_SECRET`
(vacío ⇒ checkout usa `IzipayFake`, ver `src/shared/integrations/izipay/`).

## Prerrequisito de despliegue (PR3)

Cada sucursal que deba recibir pedidos del sitio necesita un
`PuntoVenta(canal="web")` dado de alta a mano en el ERP (`POST /api/v1/
sales/puntos-venta`, `politica_pago="adelantado"` obligatorio por
RN-POS-005) con `modalidades_habilitadas` incluyendo `delivery`/`takeout`
según corresponda — una sucursal sin ese punto de venta simplemente no
aparece como candidata, sin error visible en el sitio.
