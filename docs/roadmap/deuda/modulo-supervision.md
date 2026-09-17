# Deuda técnica — Módulo supervision (slice core — deuda declarada)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ⬜ **Hora de cierre de jornada por empresa.** Hoy
  `supervision_hora_cierre_jornada` es un valor semilla único de
  `settings`, igual que `production_hora_cierre_jornada` antes de su
  propio ajuste. Migrar a `parametro_empresa` (mismo patrón que
  `production.application.reportes_jornada::hora_cierre_jornada_de`) el
  día que una empresa del grupo necesite un horario de cierre distinto.
- ⬜ **Rotación automática de responsable por turno.** La asignación hoy es
  manual (el supervisor reasigna desde el tablero cada día que hace
  falta). Los SOP de Limpieza piden rotación explícita para algunas tareas
  (`parte-superior-muebles.md`: "necesita fecha fija... rotación de
  responsable registrada"); automatizarla exige un concepto de turno de
  trabajo que hoy vive en `rrhh` y no está conectado a este módulo.
- ⬜ **Frecuencias quincenal y semestral.** `rules.FRECUENCIAS` cubre
  diaria/interdiaria/semanal/mensual; dos SOP de Limpieza piden quincenal
  (`remocion-telaranas.md`) y semestral (`limpieza-horno-piedra.md`,
  abrillantado 2×/año). Se puede modelar sobre `dia_mes` con un contador
  adicional, pero no vale la pena hasta que el catálogo de SOP realmente
  los use en producción.
- ⬜ **No existe SOP de "cierre de local" (`PROC-OPE-003`).** El registro
  maestro de `docs/domain/process-nomenclature.md` solo tiene
  `PROC-OPE-001` (apertura) y `PROC-OPE-002` (cumplimiento de pedido). El
  módulo automatiza los pasos de cierre que ya aparecen sueltos en los SOP
  de Limpieza y Caja ("al cierre de turno"), pero no hay un SOP único de
  cierre de sucursal que enumere el checklist completo — redactarlo es
  trabajo de `sop-creator`, no de este módulo.
