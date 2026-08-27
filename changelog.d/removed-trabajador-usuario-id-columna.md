- **`trabajador.usuario_id` deja de ser una columna con FK propia** (ADR-070).
  RRHH → Trabajadores pierde el selector "Cuenta para marcar asistencia": la
  cuenta con la que un trabajador marca se vincula ahora únicamente desde
  Usuarios → Cuentas → "Persona vinculada", y se deriva de
  `usuario.persona_id`. `TrabajadorCreate`/`TrabajadorUpdate` pierden
  `usuario_id`; `TrabajadorOut.usuario_id` se mantiene, ahora calculado.
