# Plantillas de documentos de Compras

Plantillas rellenables para el módulo de Compras, gestionadas desde el ERP.
Misma convención de campos que
[templates/rrhh/README.md](../rrhh/README.md):
`{{ entidad.campo }}` autocompletado, `[[ COMPLETAR: descripción ]]` manual,
`{{ hoy }}` fecha de emisión.

## Origen de datos (entidades del ERP)

Ver [data-model.md §5](../../architecture/data-model.md):
`proveedor`, `orden_compra`, `orden_compra_item`, `recepcion_compra`,
`recepcion_item`, `cotizacion`, `empresa`, `sucursal` (destino Almacén
Central).

## Plantillas

| Plantilla | Uso | Referencia |
|-----------|-----|-----------|
| [ficha-proveedor.md](ficha-proveedor.md) | Alta y condiciones de un proveedor | RN-CMP-*, marco-legal-compras.md |
| [solicitud-cotizacion-rfq.md](solicitud-cotizacion-rfq.md) | Pedido de cotización a proveedores | RN-DOC-007 |
| [orden-compra.md](orden-compra.md) | Documento formal de compra | RN-CMP-001/002 |
| [evaluacion-proveedor.md](evaluacion-proveedor.md) | Evaluación periódica de desempeño (complementa indicador automático del ERP) | — |
| [rendicion-caja-chica-compras.md](rendicion-caja-chica-compras.md) | Rendición semanal de caja chica a Contabilidad | RN-CMP-005 |
| [ficha-requerimiento-activo.md](ficha-requerimiento-activo.md) | Compra de activos/equipamiento, validada por área + gerencia | RN-MNT-001 |

## ⚠ Aviso legal

Estas plantillas son una base profesional de Compras, **no constituyen
asesoría legal ni tributaria**. Antes de su uso, validar con el contador el
tratamiento de IGV/detracciones vigente (RN-IMP-003) y con el abogado
cualquier cláusula contractual con proveedores.
