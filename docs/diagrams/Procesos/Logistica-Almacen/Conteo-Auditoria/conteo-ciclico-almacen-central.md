# SOP — Conteo cíclico de Almacén Central

**Área:** Almacén y Logística · **Grupo:** Conteo y Auditoría

## Objetivo
Que el stock del ERP refleje el stock físico real de forma constante — un
conteo solo antes de auditoría es demasiado tarde para corregir a tiempo.

## Frecuencia
Cíclico por categoría rotativa [[ COMPLETAR: definir frecuencia, sugerido
semanal ]]; conteo general de todo el almacén [[ COMPLETAR: sugerido
mensual o trimestral ]] (RN-INV-007, periodicidad configurable en el ERP).

## Responsable
Encargado de Almacén Central ejecuta; administrador o supervisor de
logística supervisa.

## Materiales y equipo
- ERP: módulo de inventario (registro de conteo, comparación contra stock
  del sistema)
- Balanza (insumos a granel)
- Plantilla: [reporte-conteo-ciclico](../../../../templates/almacen-logistica/reporte-conteo-ciclico.md)

## Pasos
1. Seleccionar la categoría o zona a contar según el ciclo programado
   (RN-INV-014 — conteo de rutina).
2. Contar/pesar físicamente cada artículo, sin ver el stock esperado del
   sistema primero (conteo "a ciegas" si el rol lo permite, RN-INV-005) —
   evita sesgar el conteo hacia lo que el sistema dice que debería haber.
3. Registrar el conteo físico en el ERP.
4. El sistema compara automáticamente contra el stock registrado y muestra
   la diferencia por artículo.
5. Para cada diferencia: verificar causa razonable antes de generar ajuste
   (¿hubo movimiento no registrado? ¿error de conteo? recontar si hay
   duda).
6. Si la diferencia persiste → generar solicitud de ajuste con motivo
   (sobrante, faltante, merma/daño, error de registro — RN-INV-016); pasa
   al SOP de ajuste por discrepancia si supera el margen de error.
7. Archivar el reporte de conteo del ciclo.

## Excepciones
- Diferencia dentro del margen de error acordado con Contabilidad → se
  ajusta directo sin escalar a auditoría (RN-INV-015).
- Diferencia fuera de margen → obligatorio pasar por
  [ajuste-inventario-discrepancia](ajuste-inventario-discrepancia.md), no
  se resuelve solo con el ajuste simple.
- Conteo que coincide con recepción o despacho en curso → pausar el
  movimiento en esa zona hasta terminar el conteo, para no contar a mitad
  de un movimiento.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| El conteo "siempre cuadra" pero después aparecen faltantes | Se cuenta viendo el stock esperado y se ajusta el número contado para que cuadre | Conteo a ciegas (paso 2), sin ver el esperado primero |
| Conteo cíclico se salta semanas | Sin dueño ni calendario fijo | Frecuencia fija en el ERP, no depende de "cuando haya tiempo" |
| Diferencia se ajusta sin investigar causa | Se prioriza cerrar rápido | Paso 5 obligatorio: verificar causa razonable antes de ajustar |

## Checklist de verificación
- [ ] Categoría/zona del ciclo identificada
- [ ] Conteo físico registrado sin ver el stock esperado primero
- [ ] Comparación contra sistema revisada
- [ ] Causa de cada diferencia investigada antes de ajustar
- [ ] Ajuste generado con motivo si corresponde
- [ ] Reporte archivado

## Evidencia y supervisión
Reporte de conteo por ciclo archivado en el ERP. Administrador/supervisor
revisa mensualmente el histórico de diferencias por categoría (patrón =
señal de problema estructural, no solo error puntual).
