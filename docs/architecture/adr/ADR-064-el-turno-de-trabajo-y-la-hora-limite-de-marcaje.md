# ADR-064 — El turno de trabajo es una entidad, y la hora límite vive en él

- Estado: aceptado
- Fecha: 2026-08-24
- Contexto: `rrhh` (turno_sucursal, asistencia), `users` (sucursal)
- Relacionado: ADR-014 (parámetros configurables por empresa), ADR-062 (centro
  de labores), ADR-065 (pad de asistencia), RN-RRHH-009 (no marcado no se
  considera), RN-RRHH-020/021/022, `docs/foundation/glossary.md`

## Contexto

`asistencia` existía desde el slice de ciclo laboral con `tardanza_min` y
`horas_extra`… que **los mandaba el cliente**. El ERP guardaba una tardanza que
nunca calculó, porque no tenía contra qué calcularla: no existe en ningún
módulo una entidad de **horario laboral**.

El glosario ya nombraba «horario laboral» y lo distinguía de «horario de
atención» (`sucursal.horario_atencion`, que es cuándo abre al público y lleva
escrito el aviso de que no es el horario de la gente). Lo único parecido a una
jornada era `contrato_laboral.jornada_horas_semana`: horas por semana, sin
decir cuáles.

Y la palabra **turno** ya estaba tomada: en `accounting` significa la sesión de
una caja abierta, de donde sale el encargado de turno que recibe los reportes
del local.

El encargo concreto: si alguien no marca su salida antes de cierta hora
—configurable por sucursal y por turno— hay que avisarle.

## Decisión

### 1. `turno_sucursal`: una tabla, no un parámetro

El turno de trabajo es una entidad de `rrhh` con `sucursal_id`, `nombre`,
`hora_inicio`, `hora_fin`, `tolerancia_min`, `hora_limite_salida` y `activo`.

**No va en `parametro_empresa`** (ADR-014). Ese índice es
`(empresa_id, modulo, codigo)`: para tener un valor por sucursal habría que
meter el id del local dentro del `codigo`, y ahí se pierde la FK — que es
exactamente el precedente que ADR-014 ya resolvió sacando
`categoria.frecuencia_conteo` a una columna. Además un turno no es un valor,
son cinco campos que solo tienen sentido juntos.

Lo administra RRHH (`rrhh.turno_gestionar`) y no organización: el horario
laboral es materia de planilla, no de infraestructura del local.

### 2. La hora límite vive en el turno, no en la sucursal

Es lo que hace que «por sucursal y turno» funcione sin una segunda tabla de
excepciones: el turno mañana de Castilla vence a las 18:00 y el de noche a las
03:00 del día siguiente, y los dos son del mismo local. Una columna en
`sucursal` habría obligado a elegir una sola hora para los dos.

`hora_limite_salida` **menor** que `hora_inicio` significa que el turno cruza
la medianoche. No hay bandera de «turno nocturno»: el orden de las horas ya lo
dice, y una bandera que puede contradecir a los datos que la rodean es una
bandera que algún día los contradice.

### 3. El turno de la marcación lo elige el servidor

`asistencia.turno_id` (nullable) guarda contra qué turno se midió. Lo resuelve
`turnos.turno_vigente`: el turno activo cuya ventana
`[hora_inicio − tolerancia, hora_fin]` contiene el momento, y ante empate el de
`hora_inicio` más cercana — el cambio de turno siempre se pisa un poco, y quien
marca a las 15:05 entra al de las 15:00, no al de la mañana que todavía no
termina.

No se le pregunta a quien marca. Pedirle el turno sería pedirle que se
autoevalúe la tardanza, y agrega un toque a una pantalla que tiene que
resolverse en dos.

Sin turno configurado se marca igual, con `tardanza_min = 0`. Que el local no
tenga turnos cargados no puede impedirle a nadie fichar: la falta es de
configuración, y el costo de tratarla como falta del trabajador es que deje de
marcar.

### 4. No se generan horas extra. Nunca

La columna `horas_extra` se queda, pero **solo la escribe RRHH a mano**. El pad
manda siempre 0, y quedarse pasada la hora límite produce un aviso, no un
saldo a pagar (RN-RRHH-022).

Es una decisión de negocio, no técnica: en el grupo la hora extra se autoriza
antes, no se deduce después de un reloj. Calcularla sola convertiría cada
demora en la limpieza en una obligación laboral que nadie aprobó.

## Consecuencias

- `tardanza_min` pasa a ser un dato que el ERP calcula y puede defender, en vez
  de un número que el cliente informaba.
- Aparece un tercer significado que ordenar en el glosario: **turno de
  trabajo** (rrhh) vs **turno de caja** (accounting) vs **horario de atención**
  (sucursal). Los tres quedan escritos con su distinción.
- El aviso de salida sin marcar (`rrhh.salida_sin_marcar`) tiene por fin una
  hora contra la cual estar vencido — ver ADR-065.
- Queda pendiente: nadie asigna todavía un trabajador a **su** turno de forma
  fija. Hoy el turno se infiere de la hora en que marca, que alcanza para
  medir tardanza y vencimiento pero no para armar un rol de turnos ni para
  detectar a quien no vino. Está anotado como deuda.
