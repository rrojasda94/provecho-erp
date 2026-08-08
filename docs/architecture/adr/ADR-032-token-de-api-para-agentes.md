# ADR-032 — Token de API para cuentas de agente (`agente_ia`)

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

`usuario.tipo` distingue `humano` de `agente_ia` desde el primer slice, pero
la autenticación es una sola: username + PIN de 6 dígitos → access token de
15 minutos + refresh rotativo de 7 días. Todo eso está diseñado alrededor de
una persona parada frente a un terminal.

Un agente no es esa persona. El hub de sucursal (ADR-009) se autentica hoy
con `cloud_sync_username` / `cloud_sync_pin` guardados en el `.env`, y lo
mismo pasaría con n8n, el bot de pedidos o cualquier integración:

- **El PIN de 6 dígitos es un secreto débil**: un millón de combinaciones.
  Para una persona lo compensan el lockout de 5 intentos y el rate limit por
  IP; para un proceso que se autentica solo, es un secreto de producción con
  20 bits de entropía escrito en un archivo de configuración.
- **El lockout es un modo de falla nuevo**: cinco intentos fallidos apagan
  la cuenta. Un agente mal configurado deja al hub de una sucursal sin
  sincronizar hasta que alguien lo desbloquee a mano.
- **Rotar el refresh cada 7 días** obliga a un proceso desatendido a
  persistir y rotar estado. Es ceremonia humana aplicada a una máquina.
- **Revocar es todo o nada**: apagar `usuario.activo` mata todas las
  integraciones que compartan la cuenta, y no hay forma de decir "el token
  que le di a n8n en marzo".

## Decisión

**Una cuenta `agente_ia` se autentica con un token de API de larga vida
(`token_agente`), no con username + PIN.**

- El token es `prv_` + 32 bytes de `secrets.token_urlsafe` (256 bits).
- Se guarda **solo su SHA-256**, igual que `refresh_token`. El valor en
  claro sale una única vez, en la respuesta que lo crea.
- SHA-256 y no Argon2 —a diferencia del PIN— porque un secreto de 256 bits
  no se rompe por fuerza bruta y esto se verifica en **cada** request: un
  Argon2 ahí costaría ~50 ms por llamada.
- `prefijo` (los primeros 12 caracteres, `prv_` incluido) se guarda aparte
  para poder identificar *cuál* token revocar sin conocer ninguno.
- `expira_en` es opcional (NULL = sin vencimiento). Una integración
  desatendida no puede quedarse tirada un domingo porque venció un token;
  un token de prueba sí conviene que muera solo.
- `ultimo_uso_en` se actualiza como mucho una vez por hora: sirve para
  apagar lo que ya nadie usa, no para auditar llamada por llamada — eso es
  `audit_log`.
- Emitir, listar y revocar exige `users.gestionar`. Un humano **no** puede
  tener token: `POST /users/{id}/tokens` sobre una cuenta `humano` es 409.
- La verificación revalida `tipo == "agente_ia"` en cada request: convertir
  la cuenta a humana apaga sus tokens sin depender de que alguien los
  revoque a mano.

**El RBAC no cambia.** `api/deps.get_claims` mira el prefijo: si es `prv_`
resuelve el usuario contra `token_agente` y arma **los mismos claims** que
armaría un login; si no, verifica la firma del JWT. De ahí para abajo
—tenant, permisos, restricciones, auditoría— nada distingue una credencial
de la otra. El token dice *quién*; los roles siguen diciendo *qué puede*
(RN-GEN-004).

## Alternativas descartadas

- **JWT de larga vida sin fila en BD.** Cero consultas por request, pero un
  JWT no se revoca: hay que inventar una lista de revocación, que es
  exactamente la tabla que este ADR crea, y encima con la ventana en la que
  el token robado sigue siendo válido.
- **OAuth2 client_credentials.** Es el estándar y es lo correcto el día que
  haya terceros integrándose. Hoy los clientes son nuestros, corren en
  nuestra infraestructura y el intercambio `client_id`/`client_secret` →
  access token añade un round-trip y un endpoint más para llegar al mismo
  lugar. Migrar después no rompe nada: el token seguiría siendo una fila con
  su hash.
- **mTLS.** Fuerte de verdad, pero mete la gestión de certificados en un
  ERP de restaurantes cuya operación depende de que un local con internet
  intermitente siga cobrando.
- **Reusar `refresh_token` con vencimiento largo.** La tabla existe, pero su
  semántica es la cadena de rotación de una sesión humana (`sesion_id`,
  reuso ⇒ revocar toda la cadena). Colgarle un segundo significado la
  volvería ambigua justo en el código que decide si una sesión fue robada.
- **Guardar el PIN del agente en un gestor de secretos y no tocar nada.**
  Resuelve dónde vive el secreto, no que el secreto tenga 20 bits ni que el
  lockout pueda apagar una integración.

## Consecuencias

- Tabla nueva `token_agente` (migración `b3f7d21a9c04`). Nada más cambia de
  esquema.
- `GET/POST/DELETE /api/v1/users/{id}/tokens[/{token_id}]`.
- **El hub de sucursal sigue usando username + PIN** (`cloud_sync_*`):
  migrarlo al token es un cambio de despliegue —hay que rotar el secreto de
  cada local— y va aparte, anotado en ROADMAP → Deuda técnica. La
  credencial nueva ya está lista para cuando se haga.
- Los **tests siguen autenticándose como humanos**, no con este token. Lo
  que hacía caro el login en el suite —el KDF y el limiter contra un Redis
  real— ya se resolvió donde estaba (`_argon2_barato` y
  `_rate_limit_en_memoria` en `tests/conftest.py`); lo que suma este cambio
  es `auth_headers`, que emite el JWT en proceso para los tests que
  necesitan varias identidades y no quieren gastar la cuota del limiter.
  Usar la credencial de agente ahí habría hecho que el suite ejerciera un
  camino de autenticación que ningún humano usa, además de obligar a
  sembrar un token en cada fixture.
