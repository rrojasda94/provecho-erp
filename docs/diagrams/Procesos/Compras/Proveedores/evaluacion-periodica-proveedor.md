# SOP — Evaluación periódica de proveedor

**Área:** Compras · **Grupo:** Proveedores

## Objetivo
Detectar a tiempo al proveedor que baja de calidad, se atrasa o sube precio
sin justificación — antes de que afecte la operación de cocina o el costo.

## Frecuencia
El ERP calcula el indicador automáticamente con cada recepción; revisión
humana trimestral para proveedores de insumos críticos/recurrentes,
semestral para el resto — o inmediata si el ERP dispara una alerta.

## Responsable
El ERP genera el indicador automático a partir de entregas/recepciones; el
encargado de compras revisa y decide sobre las alertas; reporta al
administrador.

## Materiales y equipo
- Plantilla: [evaluacion-proveedor](../../../../templates/compras/evaluacion-proveedor.md)
  (usarla para el criterio cualitativo que el ERP no captura: trato,
  capacidad de respuesta)
- Indicador automático del ERP: % entregado a tiempo, % de conformidad en
  recepción, variación de precio — calculado de cada recepción registrada
  contra su OC, sin trabajo manual de extracción

## Pasos
1. El ERP actualiza el indicador de cada proveedor con cada recepción
   registrada (a tiempo/tarde, conforme/con diferencia, precio vs.
   histórico) — no requiere que compras lo calcule a mano.
2. El ERP genera alerta automática cuando el indicador cruza un umbral malo
   (ej. 2 entregas tarde seguidas, diferencia de cantidad repetida).
3. En la revisión periódica (o al recibir una alerta), el encargado de
   compras completa lo que el ERP no mide: retroalimentación cualitativa de
   Almacén Central y Producción/Cocina sobre calidad del insumo recibido.
4. Combinar indicador automático + retroalimentación cualitativa en la
   plantilla para la puntuación final.
5. Clasificar: proveedor preferente (mantener y priorizar), proveedor en
   observación (dar retroalimentación y plazo de mejora), proveedor a
   reemplazar (buscar alternativa activamente). El ERP refleja esta
   clasificación en la ficha para que el camino simplificado de OC (SOP
   emisión de OC) sepa a quién aplica.
6. Si "en observación" u "a reemplazar" → comunicar al proveedor los puntos
   concretos a mejorar, con plazo. Registrar la comunicación.
7. Archivar la evaluación en la ficha del proveedor.

## Excepciones
- Si un incumplimiento es grave (insumo en mal estado que afecta inocuidad,
  incumplimiento reiterado de plazo que paró producción) → evaluación
  inmediata, no esperar el ciclo; puede pasar directo a "a reemplazar".
- Proveedor único de un insumo sin alternativa en la zona → igual se evalúa
  y se documenta el riesgo, aunque no se reemplace de inmediato.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Se sigue comprando a un proveedor que falla seguido | Sin revisión de la alerta automática | El ERP alerta solo; alguien debe actuar sobre ella (paso 2-3) |
| Proveedor sube precio sin que nadie lo note | Indicador automático no revisado | Indicador de variación de precio ya lo calcula el ERP (paso 1); revisarlo |
| Cocina se queja pero compras no se entera | Sin canal de retroalimentación cualitativa | Paso 3: recoger feedback de almacén/cocina activamente, el ERP no lo capta solo |

## Checklist de verificación
- [ ] Indicador automático del ERP revisado (a tiempo, conformidad, precio)
- [ ] Alertas del periodo atendidas
- [ ] Retroalimentación cualitativa de almacén/cocina recogida
- [ ] Puntuación combinada completa en la plantilla
- [ ] Clasificación asignada (preferente / observación / reemplazar) y reflejada en el ERP
- [ ] Comunicación al proveedor si aplica, registrada
- [ ] Evaluación archivada en la ficha del proveedor

## Evidencia y supervisión
Evaluaciones archivadas por proveedor. El administrador revisa la lista de
proveedores "en observación" o "a reemplazar" cada trimestre.
