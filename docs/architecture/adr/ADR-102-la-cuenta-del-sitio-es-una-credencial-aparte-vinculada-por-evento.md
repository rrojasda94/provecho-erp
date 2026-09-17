# ADR-102 — La cuenta del sitio es una credencial aparte, vinculada a
`cliente` por evento

Fecha: 2026-09-17
Estado: aceptada

## Contexto

PR1 (ADR-101) dejó el sitio de marca en solo lectura. Este PR2 agrega
autoservicio: el cliente puede crear una cuenta (email/clave o "Continuar
con Google"), guardar varias direcciones, marcar favoritos y ver su último
pedido. El pedido explícito del usuario es que **"el acceso a clientes en
la web no garantiza acceso al ERP y viceversa, son credenciales
separadas"**.

El repositorio ya declara la intención de una cuenta de cliente:
`sales.cliente.usuario_id` es un FK opcional a `usuario` con un docstring
que dice *"cuenta propia solo para autoservicio web"*. Usar esa columna tal
cual —dar a un cliente una fila en `usuario`— significaría que la cuenta
web comparte tabla, JWT (`JWT_SECRET`) y en teoría el mismo espacio de
`roles`/`permisos` que el personal del ERP. Un bug de autorización ahí no
sería "un cliente vio su propio pedido de más", sería "un cliente entró al
back office".

## Decisión

### 1. `storefront_cuenta` es una tabla y una credencial completamente
   aparte de `usuario`

Vive en el módulo `storefront`, con su propio `password_hash` (Argon2id,
misma librería que `users` pero instancia propia — `storefront/
infrastructure/security.py` no importa `users.infrastructure.security`),
su propio `STOREFRONT_JWT_SECRET` y su propio `aud="storefront"` verificado
al decodificar. Un JWT de cuenta web:

- No decodifica contra el ERP: firmado con otro secreto, `jwt.decode` falla
  en la verificación de firma antes de mirar cualquier claim.
- Aunque alguna vez compartiera secreto por error de despliegue, seguiría
  sin servir: el ERP no valida `aud` hoy (no lo necesita, solo tiene un
  emisor), pero el decoder de `storefront` sí exige `aud="storefront"` — un
  token del ERP, sin esa claim, es rechazado igual.
- El arranque en producción falla si `STOREFRONT_JWT_SECRET` es el
  placeholder, es corto, o es igual a `JWT_SECRET`
  (`_fallas_de_secreto` en `src/config/settings.py`).

`storefront_refresh_token` es la tabla de rotación de la cuenta web, con el
mismo mecanismo que `refresh_token` del ERP (rotación + detección de
reuso revoca la sesión entera) pero sin compartir una sola fila.

`cliente.usuario_id` queda tal cual, sin usar para este caso: sigue
sirviendo para lo que sí sea una cuenta de `usuario` real (nunca se llegó a
construir un flujo que lo llenara).

### 2. El enlace a `cliente` es un evento, no un import

`storefront` no puede llamar a `sales.application.clientes.crear_cliente`
directamente — es dominio ajeno (`tests/test_arquitectura.py`). Al
registrarse, `storefront` publica `storefront.cuenta_registrada`
(`{cuenta_id, marca_id, nombres, apellidos, documento, teléfono, email,
fecha_nacimiento, dirección}`). Un listener de `sales`
(`on_cuenta_registrada`) resuelve el `grupo_id` de la marca (`users.
application.queries_publicas.grupo_de_marca`, nueva) y llama a
`clientes.crear_o_encontrar_cliente` —variante nueva de `crear_cliente`
que, si la persona ya es cliente del grupo (compraba en mostrador antes de
crear su cuenta web), devuelve ese `cliente` en vez de fallar con
`Conflicto`—. Publica de vuelta `sales.cliente_vinculado`
(`{cuenta_id, cliente_id}`), que un listener de `storefront` consume para
guardar `cliente_id` en la cuenta.

Mismo patrón que la convergencia `sales`↔`delivery` de ADR-098: dos
eventos, cada módulo dueño de su escritura, ninguno importa el dominio del
otro. Costo aceptado igual que ahí (ADR-016, best-effort): si el listener
de `sales` falla, la cuenta queda sin `cliente_id` hasta que algo la
reconcilie — no bloquea el registro ni el login, y el cliente no nota nada
salvo que "tu último pedido" no aparece todavía.

### 3. Google Sign-In verifica el `id_token` contra las claves de Google,
   nunca confía en el navegador

`storefront/infrastructure/google_auth.py` usa `jwt.PyJWKClient` (ya viene
con PyJWT, sin dependencia nueva) contra el JWKS público de Google,
validando firma, emisor y `aud=GOOGLE_OAUTH_CLIENT_ID`. Una cuenta nueva
por Google exige los mismos datos que el registro por clave —Google
confirma el email, no el DNI, el teléfono ni el cumpleaños (RN-WEB-005)—.
Un email que ya tenía cuenta por clave se vincula (`google_sub` se agrega
a la fila existente) en vez de duplicarse.

### 4. La superficie de cuenta escribe con las mismas guardas que el resto
   de lo público del ERP

`api/cuentas_routers.py` no lleva JWT del ERP (no podría: es antes de que
exista una sesión). Rate limit por IP en cada endpoint (10/min login,
10/hora registro), lockout de 5 intentos igual que `users`
(`storefront.domain.rules`), y el mismo patrón de "commitear antes de
fallar" que `users.api.routers::login` para que un intento fallido o un
reuso de refresh persistan aunque el request termine en error — el
rollback automático de `get_db` ante una excepción no controlada, si no,
se llevaría puesto el lockout.

## Consecuencias

- Dos JWT, dos secretos, dos tablas de refresh token, dos lockouts. Es el
  costo explícito del aislamiento que pidió el usuario — compartir
  cualquiera de las dos anularía la garantía.
- `sales` gana dos funciones nuevas en su contrato público
  (`crear_o_encontrar_cliente` es interna, pero `ultimo_pedido_de_cliente`
  se suma a `queries_publicas.py`) y un listener más.
- `users` gana `grupo_de_marca` en su contrato público — lo necesita
  `sales` para resolver a qué grupo pertenece una cuenta que solo conoce su
  `marca_id`.
- El sitio de marca sigue sin frontend de pago/carrito (PR3); esta fase
  entrega cuenta, direcciones, favoritos y "tu último pedido" (de cualquier
  canal, ya que `web` como canal de venta todavía no existe).

## Alternativas descartadas

- **Reusar `usuario` con un rol "cliente" sin permisos.** Es lo que
  `cliente.usuario_id` sugería. Comparte `JWT_SECRET`, la tabla
  `refresh_token` y el espacio de RBAC del ERP — el aislamiento pedido deja
  de ser real, queda como una promesa de que nadie le asigna un permiso a
  esa fila por error.
- **Un solo secreto de JWT con un claim `aud` distinto.** Reduce el
  aislamiento a una sola comprobación de código (`aud=="storefront"`) en
  vez de dos capas independientes (secreto + `aud`). Un bug que omita esa
  comprobación en un endpoint nuevo del ERP dejaría de ser "no debería
  pasar" para ser "un token de cliente ya es válido ahí".
