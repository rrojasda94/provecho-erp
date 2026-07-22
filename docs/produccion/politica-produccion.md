# Política de Producción — Grupo Majambo

Referencia operativa del área. Spec a futuro (cocina de producción
planeada 2027, ver [README.md](README.md)). No reemplaza el criterio de
Comercial (precio/lanzamiento) ni de Contabilidad (costeo) — donde el
número no está definido, se marca `[[ COMPLETAR ]]`.

## 1. Plan de producción (cronograma)

- Plan fijo por tipo de receta/proceso (ej. lunes/miércoles/viernes:
  masa; martes/jueves: salsa) definido por Producción junto con Gerencia
  y Almacén según demanda proyectada (RN-PRD-011).
- El plan se ajusta ante pedido urgente de Almacén Central por quiebre de
  stock (RN-PRD-007/011) — la orden de producción generada por necesidad
  se vincula al plan vigente cuando encaja en un turno ya programado; si
  no, genera una orden fuera de plan, igual documentada.
- Nunca se alternan procesos incompatibles en la misma línea sin limpieza
  y desinfección intermedia documentada (RN-PRD-012) — evita
  contaminación cruzada entre tipos de receta.
- Frecuencia/detalle exacto del cronograma: [[ COMPLETAR: definir con
  Gerencia al diseñar la primera cocina de producción ]].

## 2. Control de calidad y no conformidad

- Toda orden de producción pasa control de calidad antes de habilitarse
  para despacho al almacén central (RN-PRD-013).
- Ante no conformidad, el jefe de cocina evalúa:
  - **Corregible** → reproceso (ej. reajuste dentro del margen de receta
    flexible, RN-PRD-010) → se documenta igual como hallazgo.
  - **No corregible** → se desecha como merma (RN-INV-017).
- En ambos casos se genera un `reporte_escalamiento` (origen `produccion`,
  RN-PRD-014): el jefe de cocina redacta qué encontró y qué hizo.
  Reincidencia por el mismo motivo escala a Comercial/Gerencia para
  revisar receta o proceso — mismo patrón que el escalamiento de
  atención al cliente (RN-CTP-004, ver
  [business-rules.md](../domain/business-rules.md#central-de-pedidos)).
  Un solo asiento contable posible por hallazgo: reproceso no genera
  merma ni asiento (solo el detalle de la corrección en el reporte);
  desecho sí, vía el registro de merma (RN-INV-017).
- Desechar un lote no conforme se hace dentro del establecimiento, en
  zona vigilada por cámaras (nunca fuera del local) y dentro del horario
  laboral — el video de la destrucción y el desecho final a la basura son
  la evidencia adjunta al reporte (RN-PRD-015); sin evidencia, la merma no
  se cierra. Previene que un lote "desechado" en realidad se sustraiga.
- Criterios técnicos de aceptación/rechazo por tipo de receta: [[
  COMPLETAR: ficha técnica por receta, a definir con Producción/I+D+i ]].

## 3. Inocuidad e higiene

Ya cubierto en detalle en
[business-rules.md#cocina-de-producción](../domain/business-rules.md#cocina-de-producción)
(RN-CDP-001 a 004) — resumen operativo:

- Nunca despacha directo a sucursal, solo a Almacén Central (RN-CDP-001).
- Ante posible plaga: detiene operación, solicita eliminación a empresa
  operadora, reanuda solo tras desinfección total (RN-CDP-002).
- No ingresa personal sin elementos de bioseguridad (RN-CDP-003).
- Toda devolución de SKUs sobrantes al almacén central exige guía de
  remisión (RN-CDP-004).
- Todo equipo de frío se verifica en rango de temperatura en cada
  checklist de turno; fuera de rango, el producto comprometido se marca
  "NO USAR" y se reporta de inmediato a Gerencia, sin esperar a que
  alguien redacte un reporte aparte (RN-CDP-005).
- Fecha de vencimiento de producto elaborado: normativa + análisis de
  laboratorio propio (RN-VNC-001).

## 4. Inventario de la cocina de producción

- Sigue el mismo esquema de conteo cíclico y margen de error que Almacén
  Central (RN-PRD-016, RN-INV-007/014/015), sobre su propio almacén tipo
  `produccion` (insumos, subrecetas en elaboración, producto terminado
  enfriando/empacado).
- Alimenta, junto con Almacén y Contabilidad, el cálculo de punto de
  reorden de insumos y subrecetas (RN-INV-008).
- Frecuencia exacta de conteo: [[ COMPLETAR, mismo criterio pendiente que
  Almacén Central — ver
  ../almacen-logistica/politica-almacen-logistica.md#2-conteo-y-ajuste ]].
- El reporte de conteo se genera automáticamente en el ERP a partir de
  los conteos físicos registrados (balanza/QR); el jefe de cocina visa,
  nadie lo transcribe a mano — mismo principio que el reporte de
  producción (RN-DOC-010).

## 5. Costeo real de producción (RN-PRD-018)

- El ERP calcula el costo real de cada orden automáticamente: costo de
  insumos consumidos (el insumo completo comprado — ej. el tomate
  entero, no solo la pulpa) más costo de mano de obra (horas-hombre
  registradas × tarifa de producción, definida por Contabilidad
  `[[ COMPLETAR ]]`). El jefe de cocina/cocinero solo registra
  horas-hombre; nunca calcula el costo a mano.
- Cada insumo tiene un desperdicio esperado definido en su receta
  (`receta_item.merma_pct` + tipo, ej. tomate → cáscara y semilla). El
  desperdicio real de la orden se registra por insumo, con su tipo y
  peso (pesado en balanza), y se contrasta contra lo esperado — toda
  desviación relevante queda visible por fila, no se diluye en un
  promedio.
- El costo real unitario del producto aprovechable resulta de dividir
  (costo de insumos + costo de mano de obra) entre la cantidad producida
  aprovechable — insumo del margen de contribución real que usa
  Comercial (`ficha-precio-margen.md`).

## 6. Soporte a I+D+i y Comercial

- Toda propuesta de nuevo producto o mejora de receta pasa por evaluación
  técnica de Producción/I+D+i (costo real de insumos, tiempo de
  preparación, ajuste sugerido, viabilidad) antes de que Comercial
  comprometa fecha de lanzamiento (RN-PRD-017) — formato en
  [ficha-requerimiento-nuevo-producto.md](../templates/comercial/ficha-requerimiento-nuevo-producto.md).
- Toda modificación de receta/subreceta ya aprobada genera reporte,
  actualiza costos, y notifica con urgencia a los involucrados en su
  fabricación (RN-PRD-009) — no se cambia una receta en producción sin
  que la cocina se entere el mismo día.

## Referencias

- Reglas de negocio: RN-PRD-*, RN-CDP-*, RN-VNC-*, RN-INV-007/008/014/015/017 en [business-rules.md](../domain/business-rules.md)
- Glosario: Cocina de Producción, Jefe de Cocina, Subreceta, Lote, Reporte de Producción en [glossary.md](../foundation/glossary.md)
- SOPs del área: [docs/diagrams/Procesos/Produccion/](../diagrams/Procesos/Produccion/)
- Spec técnica del módulo: [src/modules/production/README.md](../../src/modules/production/README.md)
