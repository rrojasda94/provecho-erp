- **Módulo `assets`: activos, mantenimiento, combustible y documentos con
  vencimiento** (2026-09-09, ADR-098). Nada de esto tenía código —solo
  especificación desde julio y una decisión explícita de no crear
  `vehiculo` (ADR-027 §4)—, y el usuario lo pidió directamente: registro de
  equipos y vehículos, kilometraje y consumo de combustible con detección
  de anomalía (RN-VEH-006/007), cronograma de mantenimiento con aviso
  anticipado por días y/o kilometraje (RN-MNT-005), y permisos/certificados
  con fecha de vencimiento (SOAT, revisión técnica, licencia de
  funcionamiento, Defensa Civil, fumigación, carné de sanidad, licencia de
  conducir — RN-DOC-001..004). El combustible se compra en `purchases`
  (compra directa sobre un artículo `tipo="servicio"`, ADR-082) y `assets`
  solo liga el comprobante ya recibido al vehículo — sin flujo de gasto
  propio. Las alertas usan el catálogo cerrado de `reports` que ya existía
  (ADR-033): cinco emisiones nuevas, un barrido diario idempotente por
  ventana, cero mecanismo nuevo. `flota`, el alta automática desde una OC
  tipo `activo` y la depreciación en `accounting` quedan declaradas como
  deuda, a propósito.
