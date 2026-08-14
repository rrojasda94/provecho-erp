# ADR-041 — Reseteo de PIN y consulta de documento

- Estado: aceptado
- Fecha: 2026-08-12

Dos decisiones de la misma entrega. Van juntas porque comparten el criterio
—qué se le permite a quién sobre datos de otra persona— y porque cada una sola
sería media página.

## Parte 1 — Reseteo de PIN

### Contexto

Un PIN olvidado no se recupera: está hasheado con Argon2id. Hasta ahora la
única salida era que alguien con `users.gestionar` le fijara uno a mano
(`POST /users/{id}/pin`), y el frontend ni siquiera lo ofrecía — sus
comentarios afirmaban que "lo cambia su dueño con su propia sesión", endpoint
que **no existía**. En la práctica, un trabajador que olvidaba su PIN no
entraba más.

### Decisión

**El reseteo deja el PIN por defecto y marca la cuenta.** Tres cosas pasan
juntas, y ninguna sirve sin las otras dos:

1. `usuario.debe_cambiar_pin = True` bloquea todo salvo cambiarlo. Sin esto,
   un PIN público queda vigente indefinidamente.
2. Se **revocan los refresh tokens** de esa cuenta. Un reseteo por sospecha
   que deja viva la sesión abierta no cierra nada.
3. Se **limpia el lockout**. Quien olvidó su PIN normalmente lo agotó
   intentando, y dejarlo bloqueado convierte el reseteo en nada.

**La obligación se hace cumplir en el servidor, y se lee de la base.**
`get_current_user` mira `usuario.debe_cambiar_pin` en cada request y responde
403 a todo lo que no sea verse, cambiarlo o salir
(`RUTAS_CON_PIN_TEMPORAL`). Se descartó llevarlo como claim del JWT: un claim
se congela al emitir el token, así que un reseteo no surtiría efecto hasta que
venciera el access token. Leerlo de la base cuesta nada —el usuario ya se
carga en esa dependencia— y vale en el request siguiente.

Que esto cubra **todo** el ERP no es confianza: se verificó que no hay ningún
handler que use `get_tenant` sin pasar por `get_current_user`, así que no
queda puerta lateral.

**Permiso propio `users.resetear_pin`**, aparte de `users.gestionar` en los
dos sentidos: RRHH atiende el "me olvidé el PIN" todos los lunes y no tiene
por qué poder crear cuentas ni repartir roles; y administrar usuarios no trae
de arrastre la facultad de entrar como cualquiera de ellos. **No** se le da a
`supervisor`: poder entrar como cualquiera de su turno rompe la segregación
con la que está armado el ciclo de caja (ADR-025), por el mismo motivo por el
que un encargado no se releva a sí mismo.

**Queda auditado** quién reseteó a quién: es la contracara de que un
administrador pueda dejar entrar a alguien como otro.

**El PIN por defecto es `123456` y es público** —está en `CLAUDE.md` y en el
seeder—. No pretende proteger nada: sirve para que su dueño vuelva a entrar, y
por eso la cuenta no puede hacer otra cosa hasta cambiarlo. Se evaluó generar
uno aleatorio y mostrarlo una sola vez; se descartó porque hay que dictárselo
al trabajador por teléfono o por WhatsApp, que es exactamente igual de público
y además se pierde. `cambiar_pin_propio` rechaza el PIN por defecto como valor
nuevo: cambiarlo por el mismo que puso el reseteo es no cambiarlo.

**`POST /users/me/pin` no lleva permiso** —elegir la propia clave no es un
privilegio que alguien tenga que otorgar— pero **sí exige el PIN actual**: un
token robado o una pantalla que quedó abierta no deberían alcanzar para
quedarse con la cuenta.

**La pantalla de cambio vive fuera del grupo de rutas `(app)`**, como el
login: el layout del shell manda ahí a toda cuenta marcada, y si estuviera
adentro se redirigiría a sí misma para siempre.

### Alternativas descartadas

- **Claim `pin_temporal` en el JWT**: se congela al emitir (ver arriba).
- **PIN aleatorio de un solo uso**: hay que dictárselo, con lo que deja de ser
  secreto igual, y se pierde.
- **Reusar `users.gestionar`**: obliga a darle a RRHH el CRUD de cuentas
  entero para que pueda atender un olvido.
- **Marcar y no bloquear** (solo avisar al entrar): es un cartel que se cierra
  con la X.

## Parte 2 — Consulta de DNI y RUC

### Contexto

`FactilizaClient.consultar_dni()` y `consultar_ruc()` existían desde
2026-08-02, con pruebas, y **ninguna pantalla podía usarlos**: no había
endpoint. Los helpers `nombres_desde_dni` / `razon_social_desde_ruc` aplican
el dato en el servidor al crear —así que el nombre que se guarda es el de
RENIEC (RN-PTS-004)— pero quien está tecleando no lo ve hasta después de
guardar, y descubre que el sistema escribió otro.

### Decisión

**`GET /consulta/dni/{n}` y `GET /consulta/ruc/{n}`, en `core`.** No tiene
dueño de módulo: el mismo documento lo teclean `users` al dar de alta una
persona, `purchases` al registrar un proveedor y `sales` al identificar a un
cliente en caja. Mismo criterio que el router de `audit_log`.

**Permiso propio `consulta.documento`** y no una consecuencia de poder crear
personas: cada consulta gasta cuota del proveedor y trae datos personales de
alguien que todavía no es nadie en el sistema.

**No devuelve la respuesta cruda.** El proveedor manda más de lo que la
pantalla necesita, y lo que no se manda no se filtra (Ley 29733, ADR-011).

**"No encontrado" es 200 con `encontrado: false`, no 404**: que RENIEC no
tenga ese documento no es una falla, y el alta sigue adelante tecleando.
**El proveedor caído es 502 y no 500**: el que falló es un tercero, y un 500
manda a revisar este servidor, que está bien.

**El domicilio fiscal se guarda partido** (`direccion`, `provincia`, `pais` en
`proveedor`): `provincia` es lo que decide si el flete es local o
interprovincial, y volver a partir una dirección concatenada es adivinar.
`pais` existe para el proveedor extranjero, que no tiene RUC peruano.

**Prellena, no decide.** Lo que trae se escribe en un formulario que todavía
se puede corregir —SUNAT tiene el domicilio *declarado*, que no siempre es el
almacén al que uno va a recoger— y si Factiliza no responde, el alta sigue
siendo posible tecleando (mismo criterio que ADR-005).

### Alternativas descartadas

- **Un endpoint por módulo**: tres copias de la misma llamada y tres formas de
  manejar el mismo error.
- **Colgar la consulta de `personas.leer` / `purchases.crear`**: quien puede
  registrar un proveedor podría barrer RUCs; son cosas distintas.
- **Devolver `crudo`**: datos personales que nadie pidió.
- **Guardar la dirección como un solo texto**: pierde `provincia`, que es el
  campo que se usa.

## Consecuencias

- Migración `a7c04e3b91d5` (compartida con ADR-040): `usuario.debe_cambiar_pin`
  y `proveedor.direccion`/`provincia`/`pais`.
- Permisos nuevos `users.resetear_pin` (a `rrhh_admin`) y `consulta.documento`
  (a `rrhh_admin`, `comprador`, `cajero`, `supervisor`).
- `/users/me/pin` se declara **antes** que `/users/{usuario_id}/pin`: FastAPI
  resuelve por orden y la ruta con parámetro capturaba `"me"` como si fuera un
  id, con lo que cambiar el PIN propio terminaba exigiendo `users.gestionar`.
- `GET /users/me` gana `debe_cambiar_pin`: es de lo poco que una cuenta
  bloqueada puede pedir, y el shell necesita saber a dónde mandarla.
- Queda anotado en Deuda técnica que la consulta **no tiene rate limit** propio
  (hoy solo lo tiene `/auth/login`), aunque gaste cuota de un proveedor pago.
