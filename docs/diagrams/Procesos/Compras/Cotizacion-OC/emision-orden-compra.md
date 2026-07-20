# SOP — Emisión de orden de compra (OC)

**Área:** Compras · **Grupo:** Cotización y OC

## Objetivo
Formalizar la compra en un documento único e inmutable — la OC es el
compromiso real, no el mensaje de WhatsApp al proveedor.

## Frecuencia
Cada compra a proveedor externo.

## Responsable
Encargado de compras; administrador aprueba si supera el umbral (ver SOP
aprobación).

## Materiales y equipo
- Cotización elegida (SOP solicitud de cotización)
- ERP: módulo de compras (borrador → emitida)
- Plantilla física: [orden-compra](../../../../templates/compras/orden-compra.md)
  (para proveedores que no reciben por el ERP directo)

## Camino simplificado — proveedor de confianza

Si el proveedor está clasificado "preferente" en su ficha (evaluación
periódica) y el ítem es de compra recurrente, se puede emitir la OC
**sin cotización comparativa nueva**: el sustento es el requerimiento de
almacén (qué y cuánto se necesita) + la factura recibida al final. Se salta
el paso 1 de abajo (no hace falta cotización previa) pero el resto del
proceso (emisión inmutable, umbral, seguimiento, recepción) es igual.

## Pasos
1. Crear la OC en **borrador** en el ERP con los datos de la cotización
   elegida: proveedor, ítems, cantidad, precio unitario, fecha de entrega
   requerida, condición de pago, lugar de entrega (Almacén Central).
   *(Camino simplificado: usar el precio último pactado con el proveedor en
   vez de una cotización nueva.)*
2. Verificar que el proveedor esté dado de alta y activo; si es nuevo, pasar
   primero por el SOP de alta.
3. Marcar si el ítem está sujeto a detracción (SPOT) — lo usa contabilidad
   después para el depósito antes del pago.
4. Calcular el monto total y verificar contra el umbral de aprobación
   (RN-CMP: permiso `purchases.aprobar`). Si supera el umbral → pasa a
   aprobación antes de emitir.
5. **Emitir** la OC (deja de ser borrador). A partir de aquí es
   **inmutable** (RN-CMP-001): cualquier corrección es una nueva versión o
   anulación, nunca editar la emitida.
6. Enviar la OC al proveedor (ERP, correo o impresa) y confirmar recepción
   de su parte con fecha de entrega comprometida.
7. Dar seguimiento hasta la recepción; si el proveedor no confirma en 24-48
   h, contactar directamente.

## Excepciones
- Si el proveedor cotiza distinto a lo pactado al momento de entregar → no
  se recibe a precio distinto sin nueva OC o autorización expresa del
  administrador; se documenta el desvío.
- Si la necesidad cambia después de emitida (ya no se necesita, o cambia
  cantidad) → anular la OC (con motivo) y emitir una nueva; no se "ignora".

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Nadie sabe qué se le pidió realmente al proveedor | Compra coordinada solo por WhatsApp | OC en el ERP siempre, aunque el pedido se confirme también por WhatsApp |
| Se "corrige" la OC ya emitida y se pierde el original | Edición directa en vez de nueva versión | Paso 5: emitida es inmutable, corrección = nueva versión/anulación |
| Compra grande sin que el administrador se entere | Umbral no verificado antes de emitir | Paso 4 bloqueante: sin aprobación no se emite sobre el umbral |

## Checklist de verificación
- [ ] Borrador con todos los datos de la cotización elegida
- [ ] Proveedor activo y dado de alta
- [ ] Detracción marcada si aplica
- [ ] Umbral verificado; aprobación obtenida si corresponde
- [ ] OC emitida y enviada al proveedor
- [ ] Confirmación de fecha de entrega del proveedor registrada
- [ ] Seguimiento activo hasta la recepción

## Evidencia y supervisión
OC en el ERP con su historial de estados. El administrador revisa OCs
emitidas por encima del umbral y su justificación mensualmente.
