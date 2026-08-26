- Corregido: **ningún trabajador podía marcar asistencia en el pad**. El pad
  exige `trabajador.usuario_id` para llegar al PIN que firma la marcación
  (ADR-065), pero ese campo solo viajaba en el alta: `TrabajadorUpdate` no lo
  declaraba y la pantalla de trabajadores nunca lo ofrecía, así que desde la
  UI quedaba en NULL para siempre y el 409 «el trabajador no tiene usuario con
  PIN» era el único desenlace posible, no el caso de borde que el ADR
  documentaba. Ahora la cuenta se elige al dar de alta al trabajador y al
  editarlo, y mandarla en `null` la desvincula.
- La cuenta que se asigna se valida: tiene que existir, ser de tipo `humano`
  —una de agente entra por token y no tiene PIN que teclear (ADR-032)—, estar
  activa y no ser ya de otro trabajador. Dos trabajadores con la misma cuenta
  comparten PIN, y entonces el pad no puede saber cuál de los dos fichó.
- La pantalla de trabajadores muestra en una columna quién tiene cuenta, para
  ver de un vistazo a quién le falta antes de que se pare frente al pad.
- El alta de cuenta permite vincular la persona ahí mismo: el selector solo
  estaba en «Editar cuenta», así que registrar a alguien que iba a marcar
  obligaba a crear la cuenta y volver a abrirla.
- Corregido: el tipo de cuenta «Servicio» que ofrecía el formulario no existe
  en la columna (`humano` | `agente_ia`), y elegirlo devolvía un 500 del ORM
  en vez de un error entendible. Se quitó la opción y el schema pasó a
  `Literal`, que lo rechaza como 422 antes de tocar la base.
