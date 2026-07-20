# SOP — Picking y despacho de requerimiento en almacén central

**Área:** Logística y Almacén · **Grupo:** Abastecimiento-Locales
**Basado en:** PROC-INV-001 (pasos 10-11)

## Objetivo
Preparar y despachar exactamente lo que pide cada sucursal, sin errores de
cantidad ni de producto.

## Frecuencia
Cada vez que llega un Requerimiento aprobado de una sucursal.

## Responsable
Encargado de almacén central.

## Materiales y equipo
- ERP con módulo de picking/almacén
- Balanza (si aplica pesar a granel)
- Termómetro para verificar refrigerados/congelados antes del despacho
- Material de embalaje para packing, incluyendo cajas térmicas o
  contenedores aislados para refrigerados y congelados

## Pasos
1. Recibir el Requerimiento aprobado de la sucursal en el ERP.
2. Armar el picking respetando el orden por temperatura de almacenamiento:
   primero los insumos secos/de ambiente, luego los refrigerados, y los
   congelados al final — así los productos que más se degradan pasan el
   menor tiempo posible fuera de su temperatura de conservación. No se
   despacha más de lo aprobado en la solicitud.
3. Verificar con termómetro que los refrigerados y congelados estén dentro
   de su rango de temperatura antes de embalarlos.
4. Hacer el packing agrupado por sucursal de destino y separado por zona de
   temperatura (seco, refrigerado, congelado); los congelados van al final
   del packing para cargarse últimos y ser los primeros en descargarse en
   la sucursal.
5. Entregar la mercadería al repartidor para su salida/transporte, dejando
   registrada en el ERP la transferencia como "en tránsito".

## Excepciones
- No hay stock suficiente en Almacén Central para cubrir el requerimiento
  completo → despachar lo disponible, dejar constancia en el ERP de lo no
  cubierto; no completar la diferencia con otro insumo sin autorización.
- Duda sobre si la cantidad del requerimiento es correcta → confirmar con
  la sucursal antes de armar el picking; nunca despachar más de lo
  aprobado en la solicitud.
- Sucursal lejana o demora prevista en la salida del transporte →
  reforzar con gel refrigerante/hielo seco en las cajas térmicas de
  refrigerados y congelados, no confiar solo en el orden de packing.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Congelados llegan descongelados, o refrigerados fuera de rango de temperatura | El pedido se arma sin respetar el orden por temperatura — refrigerados/congelados pasan demasiado tiempo fuera de frío durante el picking/packing | Armar el picking y packing en orden seco → refrigerado → congelado al final; cargar los congelados últimos para que sean los primeros en descargarse en destino |

## Checklist de verificación
- [ ] Requerimiento aprobado verificado antes de iniciar el picking
- [ ] Cantidad despachada igual a la aprobada, no mayor
- [ ] Todos los productos solicitados pickeados y marcados en ERP
- [ ] Picking y packing armados en orden por temperatura: seco →
      refrigerado → congelado al final
- [ ] Refrigerados y congelados verificados con termómetro antes de
      despachar
- [ ] Packing agrupado correctamente por sucursal de destino
- [ ] Transferencia registrada como "en tránsito" en el ERP al salir

## Evidencia y supervisión
El estado de la transferencia queda visible en el ERP
(`en_transito → recibida`); diferencias entre lo despachado y lo recibido
se auditan. Ver también SOP de
[recepción de requerimiento y devoluciones en local](recepcion-requerimiento-devoluciones.md).
