<!-- Plantilla: Orden de compra | Módulo Compras | Ver README.md para convención de campos -->
<!-- Uso: SOP emision-orden-compra. Emitida, es INMUTABLE (RN-CMP-001) — corrección = nueva versión o anulación. -->

# ORDEN DE COMPRA N.° [[ COMPLETAR: correlativo del ERP ]]

**{{ empresa.razon_social }}** — RUC {{ empresa.ruc }} ·
**Fecha de emisión:** {{ hoy }} ·
**Estado:** ☐ Borrador ☐ Emitida ☐ Recibida (total/parcial) ☐ Cerrada ☐ Anulada

**Proveedor:** [[ COMPLETAR: razón social ]] — RUC [[ COMPLETAR ]]
**Lugar de entrega:** {{ sucursal.nombre }} (Almacén Central) ·
**Fecha de entrega requerida:** [[ COMPLETAR ]]

## Ítems

| Ítem | Cantidad | Unidad de medida | Precio unitario | Subtotal | ¿Detracción? |
|---|---|---|---|---|---|
| [[ COMPLETAR ]] | [[ ]] | [[ ]] | S/ [[ ]] | S/ [[ ]] | ☐ Sí ☐ No |
| [[ COMPLETAR ]] | [[ ]] | [[ ]] | S/ [[ ]] | S/ [[ ]] | ☐ Sí ☐ No |

**Total:** S/ [[ COMPLETAR ]] · **Condición de pago:**
[[ COMPLETAR: contado / crédito — plazo ]]

## Aprobación (solo si supera el umbral)

☐ No requiere aprobación (monto bajo el umbral) ·
☐ Aprobada por: [[ COMPLETAR: nombre ]] — fecha: [[ COMPLETAR ]]

<br>

_______________________________
{{ emisor.nombres }} {{ emisor.apellidos }} — {{ emisor.cargo }}

---

<sub>Emitida, esta orden es inmutable (RN-CMP-001): toda corrección es una
nueva versión o una anulación registrada, nunca una edición directa. La
recepción parcial está permitida (RN-CMP-002); no recibir más de lo aquí
ordenado sin autorización expresa.</sub>
