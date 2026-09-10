- **RRHH ya puede decir cuántas horas trabajó alguien, sin exponer su ficha**
  (2026-09-09, bloque `feat/rrhh-horas-asistidas-contrato-publico` del plan de
  deuda de producción). `rrhh.application.queries_publicas` solo tenía
  `nombres_por_usuario`; se agregan `horas_asistidas` (`trabajador_id` → horas
  reales de una fecha, restando `hora_salida − hora_entrada` y sumando
  `horas_extra`, siempre 0 si la salida no está marcada — nunca una hora
  parcial que nadie puede reconstruir después) y `trabajadores_activos`
  (lista de `{id, nombre, cargo}` de la empresa, con filtro opcional por
  área). Ninguna expone remuneración, contrato ni sanciones — mismo criterio
  que el resto del contrato.
  Costo aceptado: todavía no hay ningún consumidor. Es la pieza previa a que
  `production` deje de tipear `horas_hombre` a mano (RN-PRD-018), que va en
  `feat/produccion-horas-hombre-desde-rrhh`.
