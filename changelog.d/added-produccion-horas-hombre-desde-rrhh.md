- **Las horas-hombre de una orden de producción se tipeaban a mano**
  (2026-09-09, bloque `feat/produccion-horas-hombre-desde-rrhh` del plan de
  deuda de producción, RN-PRD-018). `CompletarOrdenIn.horas_hombre` era un
  número libre pese a que RRHH ya tiene asistencia/marcación real. Ahora se
  imputan trabajadores concretos (`trabajadores[]: {trabajador_id, horas?}`):
  sin horas explícitas se imputa toda la asistencia real de hoy
  (`rrhh.queries_publicas.horas_asistidas`); con ellas, no pueden superar lo
  asistido (409), y un trabajador sin asistencia ese día tampoco se puede
  imputar (409, RN-RRHH-009). `orden_produccion.horas_hombre` pasa a ser el
  agregado (`Σ horas`) de la nueva tabla `orden_produccion_trabajador`, no
  el dato tipeado. Nuevo `GET /production/trabajadores-disponibles`
  (`rrhh.queries_publicas.trabajadores_activos`) alimenta el picker de
  trabajadores del diálogo de completar en el frontend, reemplazando el
  campo numérico de "horas hombre".
