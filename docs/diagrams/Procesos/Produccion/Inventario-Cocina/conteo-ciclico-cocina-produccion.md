# SOP — Conteo cíclico de la cocina de producción

**Área:** Producción · **Grupo:** Inventario de Cocina

## Objetivo
Que el stock del ERP refleje el stock físico real del almacén propio de
la cocina de producción (insumos, subrecetas en elaboración, producto
terminado) — mismo criterio ya aplicado en Almacén Central (RN-PRD-016).

## Frecuencia
Cíclico por categoría rotativa [[ COMPLETAR: mismo criterio pendiente que
Almacén Central, ver
[conteo-ciclico-almacen-central](../../Logistica-Almacen/Conteo-Auditoria/conteo-ciclico-almacen-central.md) ]].

## Responsable
Jefe de cocina (producción) supervisa; cocineros ejecutan el conteo
físico.

## Materiales y equipo
- ERP: módulo de inventario (almacén tipo `produccion`)
- Balanza (insumos a granel, subrecetas en elaboración)
- Plantilla: [reporte-conteo-cocina](../../../../templates/produccion/reporte-conteo-cocina.md)

## Pasos
1. Seleccionar la categoría/zona a contar según el ciclo programado
   (insumos, subrecetas en elaboración, producto terminado
   enfriando/empacado).
2. Contar/pesar físicamente cada artículo sin ver el stock esperado del
   sistema primero (mismo criterio que Almacén Central, RN-INV-005).
3. Registrar el conteo físico en el ERP.
4. El sistema compara automáticamente contra el stock registrado y
   muestra la diferencia por artículo.
5. Para cada diferencia: verificar causa razonable (¿orden de producción
   no cerrada? ¿merma no registrada? ¿error de conteo?) antes de generar
   ajuste.
6. Diferencia dentro del margen de error acordado con Contabilidad → se
   ajusta directo; fuera de margen → escalar como en el SOP de ajuste por
   discrepancia de Almacén Central (mismo criterio, RN-INV-015/016).
7. El ERP genera el reporte de conteo del ciclo automáticamente a partir
   de lo registrado en los pasos 3-6 — nadie lo redacta a mano. El jefe
   de cocina solo visa (o anota una observación si algo no cuadra con lo
   esperado) y archiva. Alimenta, junto con Almacén y Contabilidad, el
   cálculo de punto de reorden (RN-INV-008).

## Excepciones
- Conteo que coincide con una orden de producción en curso → pausar el
  registro de esa orden hasta terminar el conteo, para no contar a mitad
  de un proceso.
- Diferencia originada por merma de control de calidad no conforme ya
  registrada (ver
  [control-calidad-no-conformidad](../Calidad-Inocuidad/control-calidad-no-conformidad.md))
  → no se cuenta dos veces como discrepancia, se concilia contra ese
  reporte.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Conteo "siempre cuadra" pero después aparecen faltantes | Se cuenta viendo el stock esperado | Conteo a ciegas (paso 2) |
| Diferencia se confunde con merma ya reportada | No se concilia contra reportes de calidad | Paso de excepción: revisar reportes de no conformidad antes de generar ajuste nuevo |
| Conteo cíclico se salta por presión del cronograma de producción | Sin calendario fijo propio | Frecuencia fija en el ERP, igual que Almacén Central |
| Alguien transcribe el conteo a mano en el reporte final | Se trata el reporte como documento redactado, no generado | Paso 7: el ERP lo genera solo, el jefe de cocina visa, no transcribe |

## Checklist de verificación
- [ ] Categoría/zona del ciclo identificada
- [ ] Conteo físico registrado sin ver el stock esperado primero
- [ ] Comparación contra sistema revisada
- [ ] Diferencias conciliadas contra reportes de calidad/merma existentes
- [ ] Ajuste generado con motivo si corresponde
- [ ] Reporte generado automáticamente y visado (no transcrito a mano)

## Evidencia y supervisión
Reporte de conteo por ciclo archivado en el ERP. Administrador/jefe de
cocina revisa el histórico de diferencias, periodicidad [[ COMPLETAR ]].
