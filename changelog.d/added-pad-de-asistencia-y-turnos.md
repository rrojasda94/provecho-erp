- **El personal marca su propia asistencia** (2026-08-24, ADR-064/064,
  migración `c4d17b93e0af`). La asistencia tenía backend desde julio y
  ninguna pantalla, y marcar exigía `rrhh.asistencia_marcar` — es decir, se
  marcaba *por* la gente, no *la* gente. Ahora hay un pad a pantalla completa
  (`/asistencia`) que se abre con una **cuenta de servicio por local** (rol
  `terminal_asistencia`, un solo permiso): se toca la tarjeta con el nombre y
  se teclea el PIN propio en el mismo pinpad del PDV. La tarjeta muestra el
  nombre y nada más —la pantalla está a la vista de toda la cocina—, y el
  servidor decide la hora, el día laboral (corta a las 05:00, así el turno
  noche no se parte), si es entrada o salida y la tardanza. El PIN va contra
  el **mismo lockout del login**, con el límite contado por trabajador y no
  por IP: en un local todas las tabletas salen por la misma dirección y el
  cambio de turno son diez personas seguidas.
- **Turno de trabajo: la primera entidad de horario laboral del ERP**
  (2026-08-24, ADR-064). El glosario lo nombraba desde el principio y nada lo
  modelaba: `asistencia.tardanza_min` la mandaba **el cliente**, porque no
  había contra qué calcularla. `turno_sucursal` (nombre, entrada, salida,
  tolerancia, hora límite de marcaje de salida) se administra en RRHH →
  Turnos con `rrhh.turno_gestionar`. No fue a `parametro_empresa`: ese índice
  es por empresa y meter la sucursal en el `codigo` pierde la FK — el mismo
  precedente de `categoria.frecuencia_conteo`. Una hora de salida menor que
  la de entrada significa que el turno cruza la medianoche; no hay bandera de
  «nocturno» que pueda contradecir a los datos que la rodean.
- **Aviso de salida sin marcar** (2026-08-24, RN-RRHH-021). Un barrido horario
  encuentra las entradas sin salida cuya hora límite ya pasó y avisa por dos
  caminos: al **trabajador** en su propia campana, y al **encargado del local
  y a RRHH** con la emisión `rrhh.salida_sin_marcar`. Son dos y no uno porque
  abrir un reporte exige el permiso del módulo dueño (RN-REP-002) y un
  cocinero no tiene `rrhh.leer`: hacerlo destinatario habría sido entregarle
  algo que no puede abrir. La emisión va **sin actor**, como
  `sales.pedido_demorado` — el hecho es «falta una marcación», no «alguien
  hizo algo mal». **No se generan horas extra en ningún caso**
  (RN-RRHH-022): quedarse de más produce el aviso y nada más.
