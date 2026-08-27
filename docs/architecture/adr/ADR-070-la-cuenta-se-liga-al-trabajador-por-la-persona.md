# ADR-069 — La cuenta se liga al trabajador por la persona

- **Estado:** aceptada
- **Fecha:** 2026-08-27
- **Contexto:** `users` (`usuario`, `persona`), `rrhh` (`trabajador`, pad de
  asistencia)
- **Relacionado:** ADR-065 (el pad de asistencia y quién configura las
  pantallas), RN-RRHH-020 (el PIN que firma una marcación), RN-GEN-007
  (party model)

## Contexto

Dos síntomas reportados por el mismo usuario, en el mismo día:

1. En **Usuarios → Editar cuenta**, elegir "Persona vinculada" y guardar
   parecía no hacer nada: al reabrir el editor, el campo volvía a aparecer
   vacío.
2. El trabajador de esa misma persona **no podía marcar asistencia** en el
   pad: `409 — "el trabajador no tiene usuario con PIN: no puede marcar en
   el pad"`.

El primer síntoma era, en efecto, un bug de presentación: `PersonaPicker` es
un componente no controlado sin forma de recibir un valor inicial, así que
el modal de edición lo montaba siempre vacío aunque `usuario.persona_id`
**sí** se hubiera guardado. Ese arreglo, sin embargo, no tocaba el segundo
síntoma — y ahí estaba el problema de fondo.

El vínculo "cuenta ↔ trabajador" vivía **duplicado en dos columnas
independientes que nadie sincronizaba**:

| Columna | Se vinculaba desde | La leía |
|---|---|---|
| `usuario.persona_id` | Usuarios → "Persona vinculada" | solo el sync offline del PDV |
| `trabajador.usuario_id` | RRHH → Trabajadores → "Cuenta" | **el pad de asistencia** (`pad_asistencia.usuario_que_firma`) |

Vincular la persona desde Usuarios no habilitaba el pad — y el texto de
ayuda del formulario de alta prometía justamente lo contrario ("Hace falta
para que el trabajador pueda marcar asistencia con su PIN"), porque en algún
momento se escribió pensando en la columna equivocada. El arreglo real no
era "mostrar el campo al reabrir": era dejar de tener dos aristas para la
misma relación.

## Decisión

### `usuario.persona_id` es la única arista

La cuenta de un trabajador es la del `usuario` cuya `persona_id` coincide
con la del trabajador. Se vincula en **un solo lugar** (Usuarios → Cuentas),
y ese vínculo es lo único que el pad necesita leer.

Índice único parcial `uq_usuario_persona_viva` (`persona_id`, entre las
cuentas vivas): una persona tiene a lo más una cuenta con PIN. Sin esto, dos
cuentas sobre la misma persona dejarían al pad sin saber cuál firma —
exactamente el motivo por el que `trabajador.usuario_id` tenía su propia
regla de "una cuenta, un trabajador" del lado viejo.

### `trabajador.usuario_id` deja de ser columna: se deriva

En vez de una FK propia, el modelo la calcula con una subconsulta
(`column_property`, no `relationship`):

```sql
SELECT usuario.id FROM usuario
WHERE usuario.persona_id = trabajador.persona_id
  AND usuario.deleted_at IS NULL
LIMIT 1
```

Así, todo el código que ya leía `trabajador.usuario_id` — el pad, los avisos
de salida sin marcar, `TrabajadorOut` — sigue funcionando sin cambios; lo
único que cambia es de dónde sale el valor.

**Por qué `column_property` y no `relationship(viewonly=True,
lazy="joined")`**, que hubiera sido la forma más obvia de expresarlo: con
dos usuarios sobre una misma persona (que el índice único evita en el estado
correcto, pero que un dato viejo o una migración a mitad de camino podría
tener), un `relationship` con eager load **duplica la fila padre en
silencio** — solo emite un `SAWarning`, nada que un test capture por
accidente — y `paginar()` contaría de más: una página de 50 trabajadores
podría devolver 51 filas con `total=50`. La subconsulta con `LIMIT 1` no
puede multiplicar filas por construcción. Se verificó el caso reproduciendo
ambas formas contra el mismo dato antes de decidir.

### Una persona puede tener más de un `trabajador`

La recontratación es legítima: alguien cesa y vuelve a entrar más adelante,
y el `README` de `rrhh` ya documentaba que `postulantes.contratar_postulante`
reusa la persona del ex-trabajador en vez de duplicarla. Con la cuenta
resuelta por persona, las dos filas —la cesada y la activa— **comparten la
misma cuenta**, que es lo correcto: el PIN sigue siendo el mismo, cambió el
puesto, no la identidad.

Lo que sí hay que desempatar es el sentido inverso: `nombres_por_usuario`
(el contrato público que usa el ranking de ventas para rotular por
`usuario_id`) ahora puede encontrar dos filas `trabajador` para una misma
cuenta. Se ordena no-cesado primero y, en empate, por fecha de ingreso más
reciente — de lo contrario el ranking podía etiquetar a un cocinero
recontratado con su cargo viejo.

### `PATCH /users/{id}` pasa a `exclude_unset`, con `persona_id: null` = desvincular

`editar_usuario` saltaba **todo** valor `None`, así que desvincular una
persona era imposible por API — solo se podía reemplazarla por otra. Ahora
sigue el mismo patrón que `rrhh.trabajadores.actualizar_trabajador`: campo
ausente no toca nada, `persona_id: null` explícito desvincula.

Esto obligó a mover el router de `body.model_dump()` a
`body.model_dump(exclude_unset=True)` en el mismo cambio: sin
`exclude_unset`, cualquier PATCH parcial (por ejemplo `{"activo": false}`
desde el botón de la tabla) mandaba el resto de los campos en `None` y los
habría borrado.

### El pad valida la cuenta desactivada, y dice dónde arreglarlo

`_exigir_cuenta_asignable` — la función que validaba tipo de cuenta,
duplicados y cuenta activa al asignar `trabajador.usuario_id` — desaparece
con la columna. Sus dos primeras validaciones (una cuenta de agente no
marca, una cuenta no puede pertenecer a dos trabajadores) las cubre ahora el
índice único y el `Conflicto` de `_exigir_persona_asignable` en `users`. La
tercera —cuenta desactivada— se movió a `usuario_que_firma`: sin eso, una
cuenta inactiva caía en `verificar_pin_de` y salía como 401 "credenciales
inválidas", el mismo error engañoso que ese método existe para evitar.

### Contratar pide sucursal

De paso, `postulantes.contratar_postulante` ganó un `sucursal_id` opcional.
No es parte del vínculo cuenta↔persona, pero es la otra mitad de "por qué
un trabajador no aparece en el pad": sin centro de labores, la tarjeta nunca
se dibuja (`pad_asistencia.tarjetas` filtra por `sucursal_id`), y contratar
dejaba la ficha siempre sin sucursal.

## Alternativas descartadas

- **Sincronizar las dos columnas con un evento.** `users` publica
  `usuario_vinculado_a_persona`, `rrhh` escucha y actualiza
  `trabajador.usuario_id` (y viceversa). Sin migración destructiva, pero
  deja dos fuentes de verdad que pueden desincronizarse si alguien escribe
  fuera del evento — es el mismo problema con un paso más, no una solución.
- **Parchear solo el pad**: que `usuario_que_firma` busque la cuenta por
  persona cuando `trabajador.usuario_id` es `NULL`, sin tocar el resto.
  Arregla la asistencia hoy, pero deja la duplicación intacta —
  `nombres_por_usuario` y el selector de RRHH → Trabajadores seguirían
  leyendo la columna vieja, que puede quedar desactualizada apenas alguien
  use la pantalla de Usuarios.

## Consecuencias

- **Migración con backfill** (`d3f8a2c1e947`): mueve
  `trabajador.usuario_id` a `usuario.persona_id` donde la cuenta todavía no
  tenía persona, crea `uq_usuario_persona_viva`, y suelta la columna vieja
  (`batch_alter_table`, por la FK). Aborta — en vez de morir en la
  violación del índice — si encuentra suciedad previa: una persona con dos
  cuentas vivas, o dos trabajadores de una persona apuntando a cuentas
  distintas.
- RRHH → Trabajadores pierde el selector "Cuenta para marcar asistencia": se
  reemplaza por un aviso de solo lectura que manda a Usuarios → Cuentas.
- `TrabajadorCreate`/`TrabajadorUpdate` pierden `usuario_id`;
  `TrabajadorOut.usuario_id` se mantiene, ahora derivado.
- `UsuarioOut` gana `persona: PersonaBusquedaOut | None` — el nombre de la
  persona vinculada, no solo su id, para que el editor la pueda pintar sin
  un segundo viaje.
