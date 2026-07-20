# SOP — Recepción de compra en Almacén Central

**Área:** Compras · **Grupo:** Recepción y pago

## Objetivo
Que lo que entra a Almacén Central sea exactamente lo que dice la OC en
cantidad y calidad — recibir "a ojo" es la puerta de entrada a mermas y
sobrecostos que nadie detecta a tiempo.

## Frecuencia
Cada entrega de proveedor.

## Responsable
Personal de Almacén Central recibe; encargado de compras resuelve
discrepancias.

## Materiales y equipo
- OC emitida (referencia de cantidad, calidad y precio pactado)
- Balanza/instrumentos de medición según el insumo
- ERP: módulo de Almacén/recepción de compra

## Pasos
1. Verificar que la entrega corresponde a una OC emitida — no se recibe
   mercadería sin OC asociada.
2. Contar/pesar cada ítem contra lo indicado en la OC, no contra la guía del
   proveedor únicamente.
3. Revisar calidad: estado del insumo, fecha de vencimiento, cadena de frío
   si aplica (RN-VNC-002 y reglas de recepción de inventario).
4. Registrar la recepción en el ERP: cantidad real recibida (puede ser
   parcial, RN-CMP-002 — no recibir más de lo ordenado sin permiso
   especial), con las diferencias si las hay.
5. Si hay diferencia significativa (falta, sobra, mal estado) → no firmar 
   conformidad total; registrar la discrepancia y notificar al encargado de 
   compras antes de que el proveedor se retire.
6. La recepción conforme actualiza el costo promedio del artículo
   (RN-CMP-003) y suma stock a Almacén Central (evento a `inventory`).
7. Archivar la guía de remisión del proveedor junto a la recepción.

## Excepciones
- Si el insumo llega en mal estado → rechazar esa parte específica (no todo
  el lote si el resto está bien), registrar como devolución a proveedor y
  notificar a compras de inmediato.
- Si la cantidad recibida es mayor a la ordenada → no se acepta el exceso
  sin autorización expresa del encargado de compras (RN-CMP-002).
- Si el proveedor no puede esperar la verificación completa (prisa por
  entregar y salir) → contar al menos lo crítico del pedido antes de
  firmar; nunca firmar en blanco.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Costo promedio del insumo sale mal | Se registró cantidad distinta a la real recibida | Contar/pesar siempre contra la OC, no de memoria (paso 2) |
| Reclamo al proveedor llega tarde, ya no responde | Discrepancia detectada después de que se fue | Verificar y notificar antes de que el proveedor se retire (paso 5) |
| Se acumula mercadería sin OC en almacén | Se recibió "porque llegó" | Paso 1 bloqueante: sin OC asociada no se recibe |

## Checklist de verificación
- [ ] OC asociada verificada antes de recibir
- [ ] Cantidad contada/pesada contra la OC
- [ ] Calidad y vencimiento revisados
- [ ] Recepción registrada en ERP (total o parcial)
- [ ] Discrepancias notificadas a compras antes de que el proveedor se retire
- [ ] Guía de remisión archivada

## Evidencia y supervisión
Recepción en el ERP + guía de remisión archivada. Encargado de compras
revisa discrepancias semanalmente para retroalimentar al proveedor
(alimenta la evaluación periódica).
