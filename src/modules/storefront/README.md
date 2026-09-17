# `storefront` — Sitio web público de marca

Dueño del contenido editable, las fotos de catálogo y (a partir del PR2) las
cuentas de cliente web, direcciones, favoritos y pedidos del sitio de marca
(`charlies.majambo.com.pe`, ADR-101). Es la única puerta por la que la app
`storefront/` (un proceso Next.js aparte, sin JWT de ERP) lee al ERP.

## Alcance de este slice (PR1)

- **CMS mínimo** (`storefront_contenido`): textos editables por marca —hero,
  nosotros, contacto, trabaja, pie, seo— con claves fijas (`domain.rules`).
- **Fotos de catálogo**: subida presignada a S3 para fotos de `producto_comercial`
  e `insumo` (artículo), reusando `src.shared.adjuntos`/`src.shared.integrations.storage.s3`.
- **Superficie pública de solo lectura** (`api/publico_routers.py`, sin JWT,
  con rate limit por IP): contenido, carta con precio/ingredientes/foto,
  sucursales activas de la marca, promociones con canal `web`, convocatorias
  publicadas.

No publica ni consume eventos en este slice (no hay listeners.py). PR2 agrega
cuentas (`storefront.cuenta_registrada`) y PR3 pedidos
(`storefront.pedido_web_confirmado`).

## Regla de oro (RN-WEB-001)

La superficie pública **nunca** devuelve: `empresa_id`/`grupo_id`, costos,
datos de `persona` (DNI, teléfono, dirección de terceros), remuneración,
usuarios/proveedores, cantidades de receta. Solo los campos enumerados en
cada `*PublicoOut` de `api/schemas.py`. Ver `docs/domain/business-rules.md`
RN-WEB-001..004.

## Dependencias (contrato público, nunca dominio ajeno)

- `sales.application.queries_publicas`: `carta_publica`, `marca_de_producto`,
  `promociones_web_vigentes`, `marca_publica`.
- `inventory.application.queries_publicas`: `insumos_de_recetas`, `articulos_publicos`.
- `users.application.queries_publicas`: `sucursales_publicas_de_marca`, `empresas_de_marca`.
- `rrhh.application.queries_publicas`: `convocatorias_publicadas`.

## Endpoints

Gestión (JWT + `storefront.leer`/`storefront.editar`, prefix `/api/v1/storefront`):
`GET/PUT /contenido`, `POST /fotos/{entidad}/{entidad_id}/presign-upload`,
`POST/GET/DELETE /fotos/{entidad}/{entidad_id}`.

Públicos (sin JWT, prefix `/api/v1/storefront/publico`, `rate_limit("storefront_publico", 120, 60)`):
`GET /contenido`, `/carta`, `/productos/{id}`, `/ingredientes/{id}`,
`/sucursales`, `/promociones`, `/convocatorias`.

## Configuración

`STOREFRONT_MARCA_ID` (vacío ⇒ públicos responden 404 — "sitio no configurado"),
`STOREFRONT_SUCURSAL_ID` (vacío ⇒ primera sucursal activa de la marca),
`STOREFRONT_CANAL`/`STOREFRONT_MODALIDAD` (con qué lista de precios se resuelve
la carta pública — `delivery`/`delivery` por defecto), `STOREFRONT_URL_POSTULAR_BASE`.
