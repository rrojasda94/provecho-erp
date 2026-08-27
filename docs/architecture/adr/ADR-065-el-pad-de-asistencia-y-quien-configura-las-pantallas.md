# ADR-065 — El pad de asistencia se abre con la cuenta del local, y las pantallas las monta la administración

- Estado: aceptado
- Fecha: 2026-08-24
- Contexto: `rrhh` (pad de asistencia), `sales` (pantallas KDS), `users`
  (permisos, PIN)
- Relacionado: ADR-013 (pantallas fuera del shell), ADR-045/ADR-050 (pinpad),
  ADR-059 (la caja se da de alta en organización), ADR-062 (centro de labores),
  ADR-064 (turno de trabajo), RN-AUD-005, RN-PER-002, RN-RRHH-020,
  `docs/security/authorization.md`

## Contexto

Dos preguntas de gobierno que llegaron juntas, y que terminan siendo la misma:
**quién monta una pantalla y quién la usa.**

1. Las pantallas KDS las podía crear, editar y desactivar cualquier
   `supervisor`, y **nadie podía borrarlas**: el modelo tenía `deleted_at` pero
   ningún camino lo escribía. La caja (`punto_venta`), en cambio, ya era solo
   de la administración desde ADR-059.
2. La asistencia tenía backend desde el slice de ciclo laboral y **ninguna
   pantalla**. Marcar exigía `rrhh.asistencia_marcar`, que tienen RRHH y los
   supervisores — es decir, se marcaba *por* la gente, no *la* gente.

## Decisión

### 1. Montar una pantalla es acto de administración

`kds.configurar` sale del rol `supervisor`. Dar de alta, renombrar o borrar una
estación cambia por dónde pasa la comanda de **todos** los turnos, no solo del
que está en el local esa tarde; es alta de infraestructura, igual que la caja
(ADR-059). El supervisor conserva `kds.operar`: opera lo que ya está montado.

Se agrega `DELETE /kds/pantallas/{id}` — baja lógica de verdad (`deleted_at`),
gateado por `kds.configurar` y rechazado con 409 si la pantalla tiene cola:
borrarla con pedidos encima dejaría esas líneas sin dónde tacharse.
`activo=false` sigue existiendo y es otra cosa: la estación se apaga y vuelve.

Como ahora se puede borrar, el `UNIQUE (sucursal_id, nombre)` pasa a ser
**parcial** sobre las vivas (`deleted_at IS NULL`, mismo patrón que
`parametro_empresa`). Con el UNIQUE plano, borrar «Horno» por un error de
tipeo dejaba el nombre ocupado para siempre.

`GET /kds/pantallas` pasa a aceptar `kds.operar` **o** `kds.configurar`: quien
las administra tiene que poder ver lo que administra sin operar la cocina.

`punto_venta` **no** recibe DELETE. Tiene series SUNAT asignadas y darlo de
baja es un acto de identidad fiscal, no una limpieza de pantalla.

### 2. El pad lo abre una cuenta de servicio; la marcación la firma el PIN

La tablet del pasillo queda logueada con una cuenta por sucursal, rol
`terminal_asistencia`, **un solo permiso**: `rrhh.asistencia_terminal`. Con eso
lista los nombres de quienes marcan en ese local y presenta una marcación. Nada
más: una tablet robada no ve un sueldo, no toca un catálogo y —sobre todo— no
marca por nadie.

Marcar exige el PIN del propio trabajador, verificado contra el **mismo
lockout y el mismo contador de intentos del login**. Es el mismo gesto que
`POST /auth/autorizar` en el mostrador (RN-AUD-005): quien tiene la sesión
abierta no es quien firma.

Alternativa descartada: que cada trabajador **inicie sesión** para marcar. En
el cambio de turno son diez personas en fila; un login por cabeza convierte dos
toques en veinte, y la primera vez que se hace lento alguien deja la sesión
abierta y marca por los demás — que es exactamente lo que había que impedir.

`rrhh.asistencia_marcar` no cambia de significado: es el permiso de RRHH para
registrar o **corregir** una marcación desde el back-office. Son dos actos
distintos y por eso son dos permisos.

### 3. Lo que decide el servidor

La hora (reloj del servidor, hora Perú), el día laboral (antes de las 05:00 la
marcación es del día anterior, así el turno noche no se parte en dos), si es
entrada o salida (por el estado del día, no por el botón), la tardanza (contra
el turno vigente, ADR-064) y `horas_extra = 0` siempre.

El límite de intentos se cuenta **por trabajador**, no por IP: en un local
todas las tabletas salen por la misma dirección, y un límite por IP castigaría
a la cola por culpa de quien se equivocó de tarjeta.

### 4. La tarjeta muestra un nombre y nada más

Ni cargo, ni documento, ni remuneración. La pantalla está a la vista de todo el
que pase por la cocina. Un trabajador con `registra_asistencia=False`
(locación de servicios, RN-PER-002) no aparece: registrarle asistencia es
desnaturalizar el vínculo.

### 5. El aviso de salida sin marcar va por dos caminos

Un barrido horario (`rrhh.avisar_salidas_sin_marcar`) busca las entradas sin
salida cuya hora límite ya pasó, e idempotentemente
(`asistencia.reporte_salida_en`):

- **Al trabajador**, una notificación en su propia campana. Es a quien va
  dirigido el pedido, y no tiene —ni va a tener— `rrhh.leer`, que es lo que el
  motor de reportes exige para abrir un reporte (RN-REP-002). Por eso no se lo
  hace destinatario de la emisión: sería entregarle algo que no puede abrir.
- **Al encargado del local y a RRHH**, la emisión `rrhh.salida_sin_marcar`, que
  se administra desde la matriz de distribución como cualquier otro reporte.

La emisión va **sin actor** (`clave_actor=""`), igual que
`sales.pedido_demorado`: el hecho es «falta una marcación», no «alguien hizo
algo mal». Poner ahí al trabajador convertiría un recordatorio en un cargo.

## Consecuencias

- Un supervisor que hoy configuraba pantallas deja de poder hacerlo. Es el
  cambio visible de esta decisión y es intencional; la pantalla de estaciones
  ahora dice «pídele a un administrador».
- Marcar en el pad exige que el trabajador tenga usuario con PIN. Quien no lo
  tenga recibe un 409 explícito («el trabajador no tiene usuario con PIN») y su
  asistencia la registra RRHH a mano hasta que se le cree la cuenta.
  - **Corregido el 2026-08-25**: crear la cuenta no alcanzaba, porque nada la
    ataba al trabajador. `usuario_id` viajaba en el alta pero no en
    `TrabajadorUpdate`, y la pantalla de trabajadores nunca lo ofrecía, así que
    desde la UI el campo era NULL para siempre y **ningún** trabajador podía
    marcar. Se asignaba y se quitaba desde la ficha del trabajador.
  - **Reemplazado el 2026-08-27 (ADR-069)**: ese mecanismo —
    `trabajador.usuario_id` como columna propia, asignada desde RRHH →
    Trabajadores— convivía con `usuario.persona_id` (Usuarios → "Persona
    vinculada") sin que nada las sincronizara: vincular desde Usuarios no
    habilitaba el pad. `trabajador.usuario_id` dejó de ser columna; se
    deriva de `usuario.persona_id`, que pasó a ser la única arista.
- Aparece un tipo de cuenta más para administrar: una por local. Se crea desde
  `/usuarios` como cualquier otra; el seeder solo siembra el rol.
