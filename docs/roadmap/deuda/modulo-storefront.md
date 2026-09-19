# Deuda técnica — Módulo storefront (sitio de marca, PR1+PR2+PR3 — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-09-17 **PR1** (ADR-105): módulo `storefront`, app `storefront/`
  separada del ERP, sitio público de solo lectura de
  `charlies.majambo.com.pe` (home, carta con búsqueda/filtros/ingredientes
  clicables, mapa de locales, "Nosotros", "Trabaja con nosotros"), CMS de
  contenido (`storefront_contenido`) y fotos de catálogo desde el ERP
  (`/web`). Lo que deja abierto:
  - ✅ 2026-09-18 **Playwright del sitio.** Suite propia `storefront/e2e`
    (ADR-047, puertos 8110/3110): carrito → checkout de invitado → recojo en
    efectivo → confirmación, job `storefront-e2e` en CI.
  - ⬜ **Fuentes de marca sin llegar.** Isidora Black/Tusker Grotesk
    (brandbook) todavía no están en `storefront/public/fonts/`: el sitio
    corre con el fallback Anton+Archivo (Google Fonts) declarado en
    ADR-105 §12. Reemplazar cuando el brandbook las entregue como
    archivos, sin tocar el resto de `globals.css`.
  - ⬜ **Logo provisional.** `storefront/public/marcas/logo.png` viene del
    prototipo portado, no del brandbook oficial — ver
    `storefront/public/marcas/README.md`.
  - ⬜ **`storefront_marca_id` sin resolver `articulo`/`producto_comercial`
    por otra marca.** El sitio sirve una sola marca a la vez
    (`STOREFRONT_MARCA_ID`); si el grupo abre un segundo sitio de marca,
    hace falta una segunda app + un segundo `STOREFRONT_MARCA_ID` por
    dominio — no un selector dentro del mismo proceso.
  - ⬜ **Sin eventos de invalidación de caché.** No existe
    `producto.actualizado`/`sucursal.actualizada` — el sitio se refresca
    solo por el `revalidate` de 60 s de cada página. Aceptable para PR1;
    un catálogo que cambia con más frecuencia necesitaría revalidación
    on-demand (`revalidateTag`), que exige el evento primero.
  - ⬜ **Horario de un solo tramo por día en el formulario del ERP.**
    `sucursal.horario_atencion` admite varios tramos por día (`[[desde,
    hasta], ...]`), pero `organizacion/sucursales-cliente.tsx` solo edita
    uno. Un local con horario partido (ej. cierra a mediodía) necesita
    cargarse por API hasta que el formulario gane más filas.
  - ✅ 2026-09-18 **Sitemap y OG tags.** `storefront/app/sitemap.ts` (una
    entrada por producto), `metadataBase`/`openGraph`/`twitter` en
    `app/layout.tsx`, JSON-LD Restaurant en el layout y en `/locales`,
    JSON-LD Product en `/carta/[id]` con `openGraph.images`.
  - ⬜ **`docker-compose.prod.yml` no tiene servicio `charlies`.** Solo se
    agregó a `docker-compose.yml` (dev) y `docker-compose.staging.yml`,
    que es el único ambiente desplegado hoy (`docs/engineering/staging.md`).
    Agregarlo a producción cuando ese compose se use de verdad.

- ✅ 2026-09-17 **PR2** (ADR-104): cuentas de cliente web
  (`storefront_cuenta`), direcciones, favoritos y "tu último pedido",
  registro con email/clave o Google, vínculo a `cliente` de `sales` por
  evento (`storefront.cuenta_registrada` → `sales.cliente_vinculado`).
  Lo que deja abierto:
  - ⬜ **Sin "olvidé mi contraseña".** La cuenta web no tiene flujo de
    recuperación — a diferencia del PIN del ERP (`tests/test_reset_pin.py`),
    quien pierde su clave hoy no puede recuperarla sola.
  - ⬜ **Sin verificación de email.** El registro por email/clave deja la
    cuenta operativa de inmediato; no hay envío de correo de confirmación
    ni columna `verificada_at`.
  - ⬜ **Favoritos sin resolver a nombre/foto en `/cuenta`.** La pantalla de
    cuenta (`storefront/app/cuenta/cuenta-cliente.tsx`) solo muestra el
    conteo de favoritos y enlaza a la carta — no llama a
    `carta_publica` para mostrar nombre/foto de cada uno, para no sumar
    otra ida y vuelta a la API en esa página. Resolver si el listado de
    favoritos necesita mostrarse ahí directamente.
  - ⬜ **Anonimización ARCO (ADR-011) no extendida en código.** Declarado en
    ADR-104 §"Aislamiento y privacidad" que `storefront_cuenta`/
    `storefront_direccion` deben poder anonimizarse igual que `persona`,
    pero el flujo real de solicitudes ARCO (`rrhh`/`users`) todavía no
    conoce estas tablas.

- ✅ 2026-09-17 **PR3** (ADR-105): carrito, checkout invitado o
  logueado, asignación automática de local, ETA, boleta/factura, efectivo
  e Izipay, canal `web` en `venta`. Lo que deja abierto:
  - ⬜ **`IzipayReal` es un esqueleto.** `src/shared/integrations/izipay/`
    define el `Protocol` y `IzipayFake` (aprueba siempre); `IzipayReal`
    lanza `NotImplementedError` en sus dos métodos. Sin una cuenta de
    comercio real no hay contra qué probar el intercambio (redirección,
    firma del webhook) — completar antes de aceptar un pago real.
  - ⬜ **Sin extras ni Mitad x Mitad.** El carrito es "producto/tamaño +
    cantidad"; `sales` no tiene todavía un concepto de extra/combo del que
    colgarse (ver ADR-105 §6). Necesita diseño conjunto con el negocio
    antes de construirse.
  - ⬜ **Boleta/factura del checkout no llega al cajero en efectivo.** La
    preferencia de comprobante que el cliente tecleó vive en
    `storefront_pedido`, pero ninguna pantalla del ERP se la muestra a
    quien cobra al entregar/recoger — hoy hay que volver a pedirla, igual
    que en cualquier pedido telefónico.
  - ⬜ **Sin outbox/reconciliación real.** Si el proceso muere entre crear
    el `storefront_pedido` y publicar el evento (crash, no una excepción de
    negocio), el pedido queda `pendiente` para siempre y nadie lo repara
    solo — ADR-105 documenta por qué se prefirió no construir un outbox
    real todavía (mismo criterio que ADR-016), pero el hueco es real.
  - ⬜ **ETA y saturación fijos por `.env`, no `parametro_empresa`.** A
    diferencia de la tarifa de delivery (`delivery_radio_km`), Gerencia no
    puede tunear `STOREFRONT_ETA_*`/`STOREFRONT_SATURACION_PEDIDOS` sin un
    despliegue — aceptado para la primera versión, ver ADR-105 §4.
  - ⬜ **Tiempos de preparación sin cargar.** El estimado (RN-WEB-011) mejora
    solo donde el negocio cargó `tiempo_preparacion_min` (ficha del producto →
    "Dónde se vende y cuánto tarda"); un producto sin tiempo usa la base de
    30 min. El seeder de demo deja las pizzas en 25.
  - ⬜ **La cotización de delivery evalúa cada sucursal candidata por
    separado.** Bien para las dos sucursales actuales de Charlie's; una
    marca con muchas más necesitaría una versión que cotice en lote en vez
    de una llamada a `tarifa_delivery` por candidata.
  - ✅ 2026-09-18 **Playwright de checkout.** Cubierto por
    `storefront/e2e/checkout.spec.ts` (arriba, PR1). SEO de `/carrito`,
    `/checkout`, `/pedido/{id}` no aplica: son pasos de un flujo transaccional
    con datos del cliente, no páginas que deban indexarse.

- ✅ 2026-09-18 **PR4** (hardening): Playwright del sitio, SEO
  (`sitemap.ts`, OG, JSON-LD), auditoría (`storefront_pedido`,
  `storefront_contenido`, fotos, direcciones, cuenta) y aislamiento de
  credenciales probado a propósito con secretos forjados distintos —
  `tests/test_storefront_aislamiento_credenciales.py`. Sección propia en
  `docs/security/security.md`. No tocó la deuda de diseño ya declarada en
  PR2/PR3 (ARCO, outbox, `IzipayReal`, ETA por `.env`) — el alcance fue
  pruebas y superficie pública, no ese trabajo de producto.
