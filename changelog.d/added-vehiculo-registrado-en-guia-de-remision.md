- **La guía de remisión puede declarar un vehículo registrado en Activos**
  (2026-09-09, RN-VEH-008). `guia_remision.vehiculo_id` (sin FK — `assets`
  es otro módulo) resuelve la placa por el contrato público
  `assets.application.queries_publicas.vehiculo_para_guia` y la congela en
  `vehiculo_placa` al emitir, igual que el lugar de origen/destino. Sin
  `vehiculo_id`, `vehiculo_placa` sigue aceptando texto libre — guías
  emitidas antes de que `assets` existiera, o quien todavía no registra sus
  vehículos ahí, no cambian de flujo.
