- **Sitio público de Charlie's Pizzas: `charlies.majambo.com.pe`, PR1**
  (2026-09-17, ADR-103). App Next.js **separada** del ERP (`storefront/`,
  propia imagen de contenedor y bloque de Caddy) — a diferencia de la
  landing del QR (ADR-080), este sitio necesita SEO real, tema propio y
  una superficie de ataque acotada. Solo lectura por ahora: home con
  hero/promos web, carta con búsqueda en cliente (nombre, mal escrito,
  ingrediente — sin dependencia nueva) y filtros de precio/tamaño/
  disponibilidad, ficha de producto con ingredientes clicables (diálogo
  con foto y descripción), mapa de locales con horario y "abierto ahora",
  "Nosotros" y "Trabaja con nosotros" (enlaza a `/postular/{token}`).
  Cuentas de cliente, carrito y pagos con Izipay quedan para los slices
  siguientes (PR2/PR3).

- **Módulo `storefront`** en el backend: CMS mínimo de contenido por marca
  (`storefront_contenido`, 6 claves), fotos de catálogo (presign a S3,
  mismo patrón que `assets.documentos`) y la superficie pública
  `/api/v1/storefront/publico/*` — sin JWT, rate limit por IP, nunca
  expone empresa/grupo/costos/personas (RN-WEB-001). Lee a `sales`,
  `inventory`, `users` y `rrhh` solo por sus contratos
  `queries_publicas.py`. Columnas nuevas: `producto_comercial.descripcion`,
  `articulo.descripcion`, `sucursal.telefono`.

- **Pantalla "Sitio web" en el ERP** (`/web`, permisos `storefront.leer`/
  `.editar`): edita el contenido y sube fotos de producto/ingrediente.
  `Sucursales` gana teléfono y horario de atención público; `Promociones`
  gana el canal `web`, para promos exclusivas del sitio.
