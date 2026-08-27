- **Vincular una persona a una cuenta desde Usuarios no habilitaba al
  trabajador a marcar en el pad de asistencia, y el vínculo tampoco se veía
  al reabrir el editor** (ADR-070). El vínculo cuenta↔trabajador vivía
  duplicado en dos columnas que nadie sincronizaba —
  `usuario.persona_id` (Usuarios → "Persona vinculada") y
  `trabajador.usuario_id` (RRHH → Trabajadores → "Cuenta", la única que leía
  el pad)—, así que guardar desde Usuarios quedaba sin efecto para el pad; y
  `PersonaPicker` no aceptaba un valor inicial, así que el campo se veía
  vacío al reabrir aunque el dato sí estuviera guardado.
  `trabajador.usuario_id` deja de ser columna propia y se deriva de
  `usuario.persona_id`, que pasa a ser la única arista.
- **`PATCH /users/{id}` no dejaba desvincular una persona de una cuenta**:
  todo `None` se leía como "no tocar", así que `persona_id` solo se podía
  reemplazar por otra, nunca vaciar.
- **Contratar a un postulante dejaba la ficha siempre sin sucursal**, y sin
  centro de labores el trabajador no aparecía en el pad de asistencia de
  ningún local. `contratar_postulante` acepta ahora `sucursal_id`.
