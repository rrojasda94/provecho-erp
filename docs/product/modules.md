# Módulos

La especificación de cada módulo vive en su `README.md`
(objetivo, responsabilidades, casos de uso, eventos, API, entidades, reglas,
dependencias) y se escribe ANTES de implementar. Mapa de eventos:
[../diagrams/modules.md](../diagrams/modules.md) ·
catálogo: [../architecture/events.md](../architecture/events.md).

## Activos (F0 — especificados)

| Módulo | Especificación | Estado |
|--------|----------------|--------|
| users | [src/modules/users/README.md](../../src/modules/users/README.md) | Spec lista, implementación pendiente |
| inventory | [src/modules/inventory/README.md](../../src/modules/inventory/README.md) | Spec lista |
| sales | [src/modules/sales/README.md](../../src/modules/sales/README.md) | Spec lista |
| purchases | [src/modules/purchases/README.md](../../src/modules/purchases/README.md) | Spec lista |
| accounting | [src/modules/accounting/README.md](../../src/modules/accounting/README.md) | Abierto parcialmente (ciclo de caja), spec completa pendiente |
| rrhh | [src/modules/rrhh/README.md](../../src/modules/rrhh/README.md) | Abierto parcialmente (solo `trabajador`), spec completa pendiente |
| reports | [src/modules/reports/README.md](../../src/modules/reports/README.md) | Slice core implementado 2026-08-08 (ADR-033): emisión por evento, distribución por área/rol/usuario y matriz de gobierno. No confundir con `core/reportes`, que es la consulta bajo demanda (ADR-024) |
| assets | [src/modules/assets/README.md](../../src/modules/assets/README.md) | Slice core implementado 2026-09-09 (ADR-099): activo/vehículo, kilometraje/combustible, mantenimiento y documentos con vencimiento. El ciclo de compra sigue en `purchases` y la depreciación en `accounting` — deuda ya cerrada el mismo día, solo `flota` queda pendiente |
| delivery | [src/modules/delivery/README.md](../../src/modules/delivery/README.md) | Slices 2-6 implementados 2026-09-09 (ADR-098): repartidores, ciclo de ruta/entrega con ruteo real u heurístico, GPS, seguimiento público con mapa, PWA instalable del repartidor, tablero de despacho en el ERP y aviso al cliente por WhatsApp con fallback copiar/`wa.me` |
| storefront | [src/modules/storefront/README.md](../../src/modules/storefront/README.md) | PR1 (2026-09-17, ADR-103): CMS de contenido, fotos de catálogo y superficie pública de solo lectura para el sitio de marca `charlies.majambo.com.pe` (app `storefront/`, separada del ERP). PR2 (2026-09-17, ADR-104): cuentas de cliente (email/clave + Google), direcciones, favoritos, "tu último pedido"; credencial propia, nunca intercambiable con la del ERP. PR3 (2026-09-17, ADR-105): carrito, checkout invitado o logueado, asignación automática de local, ETA, boleta/factura, efectivo e Izipay, canal `web` en `venta`. Playwright y SEO quedan para PR4 |
| supervision | [src/modules/supervision/README.md](../../src/modules/supervision/README.md) | Slice core implementado 2026-09-17 (ADR-102): categorías, plantillas por sucursal o marca, generación diaria, checklist + foto con EXIF leído en servidor, cierre de jornada e informe diario emitido a `reports` |

## Futuros (se especifican antes de construirse)

requests/logistics (solicitudes, picking, transporte — parte ya vive en
`inventory`), crm, proyectos, bi/reportes, settings (ajustes/branding por
marca). `production`, `rrhh`, `activos` (`assets`) y `supervisión` ya están
construidos — esta lista quedó desactualizada respecto a la decisión de
2026-08-05 sobre módulos transversales; corregirla es deuda transversal, no
de este módulo.

## Reglas

- Un módulo = una carpeta autocontenida en `src/modules/`.
- Se activa registrando su router y sus handlers de eventos en `core`;
  se desactiva no registrándolos.
- Comunicación entre módulos SOLO por eventos o contratos públicos.
- Cada módulo trae sus tests, sus migraciones y su README actualizado.
- Si el README crece demasiado, se expande a `src/modules/<módulo>/docs/`
  junto al código — nunca a un árbol paralelo en `docs/`.
