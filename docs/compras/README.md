# Área de Compras — Grupo Majambo

Gestiona proveedores y el ciclo completo de abastecimiento externo:
cotización → orden de compra → recepción en Almacén Central → pago. La
ejecuta un **encargado de compras** dedicado; el administrador/gerente
aprueba compras sobre el umbral definido y altas de proveedores nuevos.

## Tres caminos de compra

No toda compra pasa por cotización y OC formal. Según el tipo de proveedor y
de compra:

1. **Compra menor a proveedor informal** (mercado, supermercado, proveedor
   sin capacidad de recibir OC) → sin OC, se paga con **caja chica de
   compras** y se sustenta con boleta/factura.
2. **Compra a proveedor de confianza recurrente** (ya evaluado, historial
   bueno) → **OC directa sin cotización comparativa**, sustentada con el
   requerimiento de almacén + factura. Se recomienda no comparar cada vez
   (ver criterio en el SOP de solicitud de cotización); la comparación
   vuelve en la evaluación periódica del proveedor, no en cada compra.
3. **Compra estándar o de activo/equipamiento** → cotización comparativa
   (RFQ) → OC → aprobación si supera el umbral. Los activos/equipamiento
   además se evalúan **con el área solicitante y con gerencia** antes de
   comprar (especificaciones correctas, precio competitivo).

## Flujo completo (camino 3, el más largo — los otros dos saltan pasos)

```
Necesidad detectada (punto de reorden, requerimiento de área, activo nuevo)
  → 1. Alta y evaluación del proveedor (si es nuevo)
  → 2. Solicitud de cotización (RFQ) a 1+ proveedores — con validación de
       área solicitante + gerencia si es activo/equipamiento
  → 3. Emisión de orden de compra (OC)
  → 4. Aprobación de OC (si supera el umbral)
  → 5. Recepción de mercadería en Almacén Central
  → 6. Conformidad y registro del comprobante → pasa a Contabilidad
  → 7. Contabilidad ejecuta el pago al proveedor en el plazo indicado
  → (periódico) Evaluación de proveedor — automática en el ERP a partir de
       entregas/recepciones, con revisión humana de alertas
```

Cada paso tiene su SOP en
[docs/diagrams/Procesos/Compras/](../diagrams/Procesos/Compras/):
`Proveedores/` (paso 1 y evaluación periódica), `Cotizacion-OC/` (pasos 2-4),
`Recepcion-Pago/` (pasos 5-7), `Caja-Chica/` (camino 1),
`Activos-Equipamiento/` (compras de activos, cruza con Contabilidad/Gerencia).

## Documentos del área

| Documento | Contenido |
|---|---|
| [marco-legal-compras.md](marco-legal-compras.md) | Régimen Amazonía (IGV), comprobantes, detracciones (SPOT), plazos de pago, compras centralizadas |
| [perfiles/](perfiles/) | Perfil del encargado de compras |
| [../templates/compras/](../templates/compras/) | Ficha de proveedor, solicitud de cotización, orden de compra, evaluación de proveedor |

## Principios del área

- **Toda compra externa entra por Almacén Central o queda sustentada en
  caja chica** — ninguna sucursal compra directo a proveedor externo por su
  cuenta.
- **Sin comprobante no hay pago** (RN-CMP-005/006) — ni con proveedor de
  confianza, ni con caja chica.
- **Toda OC queda en el ERP** desde el borrador; emitida es inmutable
  (RN-CMP-001) — corrección es nueva versión o anulación, nunca editar la
  original.
- **Proveedor nuevo pasa por alta y verificación** antes de la primera OC —
  RUC activo/habido (si aplica), capacidad de facturar, condición de pago
  acordada. Proveedores informales (mercado/supermercado) se registran
  igual, sin ficha de OC.
- **Con proveedor de confianza no se re-cotiza cada compra** — la
  comparación se concentra en la evaluación periódica, no en cada OC.
- **Compras compra, Contabilidad paga** — el encargado de compras registra
  y sustenta el comprobante; el pago al proveedor lo ejecuta Contabilidad en
  el plazo indicado por la ficha del proveedor.
- **Compra de activo/equipamiento se valida con el área que lo pide y con
  gerencia** antes de emitir OC — especificación correcta y precio
  competitivo, no solo disponibilidad.
- Compras que originan mantenimiento de equipos/vehículos siguen RN-MNT-002
  a 004 (coordinación con proveedor de servicio, reporte a compras).
