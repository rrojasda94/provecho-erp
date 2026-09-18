# Módulos

La especificación de cada módulo vive en su `README.md`
(objetivo, responsabilidades, casos de uso, eventos, API, entidades, reglas,
dependencias) y se escribe ANTES de implementar. Mapa de eventos:
[../diagrams/modules.md](../diagrams/modules.md) ·
catálogo: [../architecture/events.md](../architecture/events.md).

## Activos

Estado resumido; el vigente y su historial viven en la tabla "Estado por
módulo" de [`ROADMAP.md`](../../ROADMAP.md).

| Módulo | Especificación | Estado |
|--------|----------------|--------|
| users | [src/modules/users/README.md](../../src/modules/users/README.md) | Completo: auth JWT+PIN, RBAC con restricciones, refresh rotativo, lockout, token de agente IA, CRUD de organización, reseteo de PIN y consulta RENIEC/SUNAT, en producción desde 2026-07-25 |
| inventory | [src/modules/inventory/README.md](../../src/modules/inventory/README.md) | En curso: catálogo, stock por almacén, lote/FEFO, conteo cíclico, abastecimiento interno, recetas/variantes, devoluciones y planillas .xlsx operables de punta a punta; deuda menor pendiente |
| sales | [src/modules/sales/README.md](../../src/modules/sales/README.md) | En curso: PDV, KDS y catálogo de venta operativos (mesas, cupones, cocina por estaciones, variantes/restas, delivery); falta el motor de promociones condicionales completo y la tarifa de delivery por sucursal |
| purchases | [src/modules/purchases/README.md](../../src/modules/purchases/README.md) | En curso: ciclo de OC completo con idempotencia y umbral configurable, recepción a inventario, conformidad de comprobante y compra directa; falta caja chica para compra directa y reconciliación completa con contabilidad |
| production | [src/modules/production/README.md](../../src/modules/production/README.md) | Slice core implementado 2026-07-25 (orden de producción, consumo, calidad, costeo); sin operación real hasta la primera cocina de producción central, planeada para 2027 |
| accounting | [src/modules/accounting/README.md](../../src/modules/accounting/README.md) | En curso: PCGE, periodos, asientos automáticos/manuales, libro mayor, estados financieros, ciclo de caja/custodia y pago a proveedor (tesorería vive aquí); falta la fecha real del asiento y el registro de préstamos/traspasos |
| rrhh | [src/modules/rrhh/README.md](../../src/modules/rrhh/README.md) | En curso: ciclo laboral, contratación/convocatoria, ARCO de postulante, asistencia con pad y terminal de marcaje, legajo y permisos; boletas y liquidaciones siguen solo por API a propósito |
| marketing | [src/modules/marketing/README.md](../../src/modules/marketing/README.md) | En curso: campañas, calendario de contenido, leads con atribución, encuestas por WhatsApp y evaluación de agencias (ADR-029/030); queda deuda declarada |
| reports | [src/modules/reports/README.md](../../src/modules/reports/README.md) | Slice core implementado 2026-08-08 (ADR-033): emisión por evento, distribución por área/rol/usuario y matriz de gobierno. No confundir con `core/reportes`, que es la consulta bajo demanda (ADR-024) |
| assets | [src/modules/assets/README.md](../../src/modules/assets/README.md) | Slice core implementado 2026-09-09 (ADR-099): activo/vehículo, kilometraje/combustible, mantenimiento y documentos con vencimiento. El ciclo de compra sigue en `purchases` y la depreciación en `accounting` — deuda ya cerrada el mismo día, solo `flota` queda pendiente |
| delivery | [src/modules/delivery/README.md](../../src/modules/delivery/README.md) | Completo (MVP): slices 1-6 implementados 2026-09-09 (ADR-098): repartidores, ciclo de ruta/entrega con ruteo real u heurístico, GPS, seguimiento público con mapa, PWA instalable del repartidor, tablero de despacho en el ERP y aviso al cliente por WhatsApp con fallback copiar/`wa.me` |
| storefront | [src/modules/storefront/README.md](../../src/modules/storefront/README.md) | PR1 implementado 2026-09-17 (ADR-103): CMS de contenido, fotos de catálogo y superficie pública de solo lectura para el sitio de marca `charlies.majambo.com.pe` (app `storefront/`, separada del ERP). Cuentas de cliente, carrito y pagos quedan para PR2/PR3 |
| supervision | [src/modules/supervision/README.md](../../src/modules/supervision/README.md) | Slice core implementado 2026-09-17 (ADR-102): categorías, plantillas por sucursal o marca, generación diaria, checklist + foto con EXIF leído en servidor, cierre de jornada e informe diario emitido a `reports` |

## Futuros (se especifican antes de construirse)

requests/logistics (solicitudes, picking, transporte — parte ya vive en
`inventory`), crm, proyectos, settings (ajustes/branding por marca).
`production`, `rrhh`, `marketing`, `assets`, `delivery`, `storefront`,
`supervision` y los reportes/BI (`reports` + `core/reportes`) ya están
construidos y figuran arriba.

## Reglas

- Un módulo = una carpeta autocontenida en `src/modules/`.
- Se activa registrando su router y sus handlers de eventos en `core`;
  se desactiva no registrándolos.
- Comunicación entre módulos SOLO por eventos o contratos públicos.
- Cada módulo trae sus tests, sus migraciones y su README actualizado.
- Si el README crece demasiado, se expande a `src/modules/<módulo>/docs/`
  junto al código — nunca a un árbol paralelo en `docs/`.
