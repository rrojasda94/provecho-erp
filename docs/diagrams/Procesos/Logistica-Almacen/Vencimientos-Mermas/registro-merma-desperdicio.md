# SOP — Registro de merma y desperdicio en almacén

**Área:** Almacén y Logística · **Grupo:** Vencimientos y Mermas

## Objetivo
Que toda pérdida quede documentada con causa real — la merma que no se
registra no se puede reducir, solo se repite.

## Frecuencia
Cada vez que se detecta merma o desperdicio en el almacén.

## Responsable
Encargado de Almacén Central.

## Materiales y equipo
- Plantilla: [reporte-merma-desperdicio](../../../../templates/almacen-logistica/reporte-merma-desperdicio.md)
- ERP: módulo de inventario (registro de merma con motivo)

## Pasos
1. Identificar el artículo y cantidad afectada al detectar la merma
   (vencimiento no rotado a tiempo, daño físico, error de manejo).
2. Clasificar la causa: vencimiento, daño en manipulación, daño de
   transporte, error de recepción no detectado a tiempo, plaga, otro.
3. Separar físicamente el producto del stock disponible de inmediato — pasa
   a stock de merma/dañado (subtipo de stock reservado, RN-INV-012), no se
   queda mezclado con lo vendible.
4. Registrar en el ERP: artículo, cantidad, causa, valor estimado de la
   pérdida (costo del artículo).
5. Si la causa sugiere un problema recurrente (ej. mismo tipo de daño de
   transporte) → señalarlo en el reporte para revisión de proceso, no solo
   registrar la pérdida puntual.
6. Destino final del producto en merma: desecho, o auditoría si el volumen
   o la causa lo amerita (RN-INV-019).
7. Reporte mensual consolidado a Contabilidad (rinde cuentas del área,
   RN-INV-017).

## Excepciones
- Desperdicio que puede asociarse como producto derivado de una receta
  (ej. recorte reutilizable) → coordinar con Producción antes de desechar,
  no es automáticamente pérdida total (RN-INV-018).
- Merma por causa externa evidente (ej. corte de luz prolongado que afectó
  cadena de frío) → documentar la causa externa, puede eximir de
  responsabilidad individual en la revisión.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Merma "desaparece" del stock sin registro | Se descarta directo sin pasar por el ERP | Paso 3-4 obligatorios antes de desechar |
| Mismo tipo de daño se repite mes a mes | Causa raíz nunca se revisa | Paso 5: señalar patrón, no solo registrar cada caso aislado |
| Contabilidad no tiene visibilidad de la merma real | Sin reporte consolidado | Paso 7: reporte mensual obligatorio |

## Checklist de verificación
- [ ] Artículo y cantidad identificados
- [ ] Causa clasificada
- [ ] Producto separado del stock disponible (stock de merma/dañado)
- [ ] Registrado en el ERP con valor estimado
- [ ] Patrón recurrente señalado si aplica
- [ ] Destino final determinado (desecho/auditoría)
- [ ] Incluido en el reporte mensual a Contabilidad

## Evidencia y supervisión
Reporte mensual de merma a Contabilidad. Administrador revisa tendencia de
merma por artículo/causa trimestralmente — patrón repetido dispara revisión
de proceso (transporte, manejo, o compra en exceso).
