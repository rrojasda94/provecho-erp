# SOP — Plan de producción (cronograma fijo + ajuste por necesidad)

**Área:** Producción · **Grupo:** Planificación

## Objetivo
Que la cocina de producción trabaje según un cronograma metódico por tipo
de receta/proceso — evitando contaminación cruzada — y a la vez responda
a tiempo cuando Almacén Central reporta un quiebre de stock urgente.

## Frecuencia
Cronograma base [[ COMPLETAR: definir con Gerencia, sugerido semanal por
tipo de receta ]]; ajuste por necesidad, cada vez que Almacén Central
genera una alerta de stock mínimo (RN-PRD-007).

## Responsable
Jefe de cocina (producción) define y ejecuta el plan; Gerencia y Almacén
aportan la demanda proyectada.

## Materiales y equipo
- ERP: módulo de producción (plan de producción, órdenes de producción)
- Plantilla: [orden-produccion](../../../../templates/produccion/orden-produccion.md)

## Pasos
1. Definir el plan de producción de la semana/periodo: qué receta/tipo de
   proceso se produce cada día o turno, agrupando procesos compatibles
   para evitar contaminación cruzada (RN-PRD-012).
2. Registrar el plan en el ERP (`plan_produccion`): fecha, turno, línea de
   producción/tipo de receta.
3. El sistema genera las órdenes de producción del plan (`orden_produccion`
   vinculada a `plan_produccion_id`).
4. Ante alerta de stock mínimo de Almacén Central (RN-PRD-007/011): evaluar
   si encaja en un turno ya programado del plan vigente — si sí, se
   vincula al plan; si no, se genera una orden fuera de plan, igual
   registrada y priorizada.
5. Ejecutar cada orden de producción: registrar insumo consumido, peso de
   desperdicio real por tipo (contra lo esperado en `receta_item.merma_pct`)
   y horas-hombre trabajadas — el ERP calcula el costo real de la orden
   automáticamente (insumos + mano de obra, RN-PRD-018), nadie lo calcula
   a mano (ver
   [control-calidad-no-conformidad](../Calidad-Inocuidad/control-calidad-no-conformidad.md)
   para el paso de control de calidad antes de cerrarla).
6. Al cierre de jornada, el ERP consolida el reporte de producción
   (RN-DOC-010) con lo ejecutado del plan y lo generado por necesidad.

## Excepciones
- Necesidad urgente que no cabe en ningún turno disponible del cronograma
  → el jefe de cocina prioriza y documenta el desvío del plan (no se
  descarta la necesidad de Almacén por respetar el cronograma a rajatabla).
- Cambio de receta/subreceta durante el periodo del plan (RN-PRD-009) →
  el plan y las órdenes pendientes se actualizan el mismo día,
  notificación urgente a quienes fabrican.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Se alternan procesos incompatibles en la misma línea | Cronograma no agrupa por tipo de proceso | Agrupar por línea/tipo de receta (paso 1); limpieza intermedia documentada si es inevitable alternar |
| Producción reactiva 100% a pedidos, sin plan base | No hay cronograma fijo, solo apaga incendios | Definir plan base (paso 1-2) antes de aceptar que todo sea ajuste por necesidad |
| Orden fuera de plan no queda registrada | Se prioriza velocidad sobre registro | Paso 4 obligatorio: toda orden, dentro o fuera de plan, se registra en el ERP |
| Costo real de la orden se estima "a ojo" | No se registran horas-hombre ni desperdicio real por insumo | Paso 5: registrar ambos, el ERP calcula el costo, no se aproxima manualmente |

## Checklist de verificación
- [ ] Plan de producción del periodo registrado en el ERP
- [ ] Órdenes de producción generadas y vinculadas al plan
- [ ] Alertas de Almacén Central evaluadas contra el plan vigente
- [ ] Órdenes fuera de plan documentadas con motivo
- [ ] Desperdicio real por insumo y horas-hombre registrados por orden
- [ ] Reporte de producción de la jornada consolidado

## Evidencia y supervisión
Plan de producción y órdenes archivados en el ERP. Gerencia revisa
cumplimiento de cronograma vs. desvíos por necesidad, periodicidad
[[ COMPLETAR ]].
