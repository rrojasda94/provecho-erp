# Deuda técnica — Módulo storefront (sitio de marca, PR1 — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-09-17 **PR1** (ADR-101): módulo `storefront`, app `storefront/`
  separada del ERP, sitio público de solo lectura de
  `charlies.majambo.com.pe` (home, carta con búsqueda/filtros/ingredientes
  clicables, mapa de locales, "Nosotros", "Trabaja con nosotros"), CMS de
  contenido (`storefront_contenido`) y fotos de catálogo desde el ERP
  (`/web`). Lo que deja abierto:
  - ⬜ **Sin Playwright del sitio.** `frontend/e2e`/`frontend/uso` no cubren
    `storefront/` — queda para PR4 (hardening), junto con el resto de la
    verificación de punta a punta.
  - ⬜ **Fuentes de marca sin llegar.** Isidora Black/Tusker Grotesk
    (brandbook) todavía no están en `storefront/public/fonts/`: el sitio
    corre con el fallback Anton+Archivo (Google Fonts) declarado en
    ADR-101 §12. Reemplazar cuando el brandbook las entregue como
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
  - ⬜ **Sin sitemap ni OG tags.** `storefront/app/robots.ts` permite
    indexar, pero no hay `sitemap.ts` ni metadata Open Graph por producto —
    parte de PR4 (SEO).
  - ⬜ **`docker-compose.prod.yml` no tiene servicio `charlies`.** Solo se
    agregó a `docker-compose.yml` (dev) y `docker-compose.staging.yml`,
    que es el único ambiente desplegado hoy (`docs/engineering/staging.md`).
    Agregarlo a producción cuando ese compose se use de verdad.
