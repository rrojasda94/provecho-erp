# Módulo `production` — Producción de subrecetas

**Estado (2026-07-20):** spec técnica, sin implementación — primera
cocina de producción planeada para 2027 (`docs/produccion/README.md`).
Documentado antes por dependencia de otros módulos: `inventory` ya
referencia `production.orden_completada` como evento consumido.

## Objetivo

Planificar y ejecutar la elaboración de subrecetas en cocina de
producción según cronograma + necesidad de Almacén Central, con control
de calidad obligatorio y trazabilidad completa por lote.

## Entidades

`plan_produccion` (cronograma: fecha, turno, línea de producción/tipo de
receta, origen `cronograma_fijo`|`ajuste_por_necesidad`), `orden_produccion`
(articulo_id subreceta, cantidad, almacen_id, plan_produccion_id opcional,
control_calidad_resultado, desperdicio/merma, costeo automático:
horas_hombre, costo_insumos, costo_mano_obra, costo_real_unitario —
RN-PRD-018), `consumo_produccion_item` (detalle de insumos consumidos por
orden: cantidad, costo_unitario, peso_desperdicio_real, tipo_desperdicio —
contrastado contra `receta_item.merma_pct`), `checklist_inocuidad_turno`
(bioseguridad, superficies, limpieza intermedia, equipos_frio JSONB,
plaga_indicio — bloquea la cocina si algo falla, RN-CDP-005),
`reporte_produccion` (jornada, visado_por, consolidado automático al
cierre). Detalle en `docs/architecture/data-model.md` §7.

`reporte_escalamiento` (origen `produccion`) es entidad transversal —
vive en `shared`, no en un módulo dueño único (`docs/architecture/
data-model.md` §6) — y `lote` está modelada por `inventory`; `production`
las reutiliza, no las duplica.

## Casos de uso

- Definir plan de producción del periodo (cronograma fijo por tipo de
  receta/proceso, evita contaminación cruzada).
- Generar orden de producción, desde el plan o por ajuste ante alerta de
  stock mínimo de `inventory` (RN-PRD-007/011).
- Ejecutar orden: consumir insumos/subrecetas, producir lote(s) con
  código y trazabilidad completa (manipulador, envasador, variables de
  proceso).
- Control de calidad de la orden antes de habilitar despacho: conforme,
  no conforme reprocesado, o no conforme desechado.
- No conformidad (cualquier resultado no conforme) genera
  `reporte_escalamiento` (origen `produccion`); desecho exige evidencia
  de destrucción adjunta (RN-PRD-015).
- Calcular costo real de la orden automáticamente (insumos consumidos +
  mano de obra) — nunca a mano; el desperdicio real por insumo se
  registra por tipo y peso, contrastado contra el esperado de la receta
  (RN-PRD-018).
- Verificar checklist de inocuidad al inicio de turno, incluyendo
  temperatura de cada equipo de frío; bloquear la cocina y alertar a
  Gerencia si algo falla (RN-CDP-002/005).
- Consolidar reporte de producción al cierre de jornada (RN-DOC-010).
- Conteo cíclico del almacén propio (tipo `produccion`), mismo esquema
  que `inventory` en Almacén Central — el reporte se genera
  automáticamente a partir de los conteos físicos registrados; el jefe de
  cocina visa, no lo redacta a mano.
- Evaluar viabilidad técnica de nuevo producto o mejora de receta a
  pedido de `sales`/Comercial (RN-PRD-017) — completa la ficha, no la
  origina.

## Reglas

- Toda orden de producción pasa control de calidad antes de despachar
  (RN-PRD-013); nunca se salta este paso por presión de cronograma.
- No conformidad siempre genera reporte de escalamiento, se corrija o se
  deseche (RN-PRD-014); desecho sin evidencia de destrucción no cierra
  el reporte (RN-PRD-015).
- Cambio de receta/subreceta notifica con urgencia a quienes fabrican y
  actualiza costos el mismo día (RN-PRD-009).
- Nunca despacha directo a sucursal, solo a Almacén Central (RN-CDP-001).
- Ningún documento de conteo o reporte de producción se llena a mano: se
  genera desde los datos ya registrados en el ERP (peso de balanza,
  lectura QR, horas-hombre); el rol humano es visar, no transcribir.
- Equipo de frío fuera de rango bloquea la cocina y alerta a Gerencia de
  inmediato (RN-CDP-005), igual criterio que la falla de frío en
  apertura de sucursal (RN-SUC-009).

## Flujo

Plan de producción (o necesidad urgente) → orden de producción → consumo
de insumos → elaboración → control de calidad → (conforme: empacado →
almacén de producción → despacho a Almacén Central) | (no conforme:
reproceso o desecho con evidencia → reporte de escalamiento).

## Relaciones

- Escucha: `inventory.stock_bajo_minimo` (dispara orden por necesidad,
  RN-PRD-007).
- Publica: `production.orden_completada` (consumido por `inventory` para
  descontar insumos y sumar producto terminado),
  `production.no_conformidad_detectada` (consumido por Comercial/Gerencia
  ante reincidencia; no notifica directo a `accounting` — un solo asiento
  contable por lote: si el resultado es `no_conforme_desechado` la orden
  registra merma_cantidad/merma_motivo, que dispara
  `inventory.merma_registrada` hacia `accounting`; si es
  `no_conforme_reprocesado` no hay merma ni asiento, solo el detalle de la
  corrección en el reporte de escalamiento),
  `production.equipo_frio_fuera_rango` (alerta inmediata a Gerencia,
  RN-CDP-005).
