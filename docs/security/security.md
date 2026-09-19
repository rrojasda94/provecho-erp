# Seguridad

Autenticación, endurecimiento, auditoría y backups. El control de acceso
(roles, permisos, restricciones por tenant) vive aparte en
[authorization.md](authorization.md). Protección de datos personales
(Ley 29733, derechos ARCO) vive aparte en
[proteccion-datos-personales.md](proteccion-datos-personales.md).

## Autenticación

- Login con username + PIN (6 dígitos) → **JWT** access (15 min) +
  **refresh token** (7 días, rotativo; reuso de token viejo revoca la cadena).
- PIN hasheado con **Argon2id**. Nunca en logs ni respuestas.
- **Ningún PIN se teclea en un campo de formulario** (ADR-045, ampliado por
  ADR-050): ni el login ni los cuatro puntos del PDV que lo piden tienen
  `<input type="password">`. Se toca en `components/pinpad/`, y el valor vive
  en el estado de React — lo que el gestor de contraseñas del navegador no ve
  no lo puede ofrecer para guardar, y un PIN guardado en la tablet de la caja
  hace que el turno siguiente entre con la cuenta del anterior (RN-AUD-005).
  Única excepción pendiente: `app/cambiar-pin/` (deuda de frontend).
- Bloqueo tras 5 intentos fallidos (ventana 15 min) — protege **una cuenta**.
  El login **distingue las tres negativas** (401 credenciales, 423 bloqueo,
  429 rate limit) y dice qué hacer con cada una; con un solo texto genérico
  las tres terminaban igual: probando de nuevo hasta bloquear la cuenta. Sin
  contador de intentos en el cliente — el estado real vive en el servidor.
- **Rate limit por IP** en `/auth/login` y `/auth/refresh` (contador en Redis,
  10 intentos por minuto por defecto) — protege el **endpoint**: el lockout
  por cuenta no frena a quien rota usernames desde una misma IP. Si Redis no
  responde el límite se desactiva (fail-open) y se registra advertencia: una
  caída de Redis no puede dejar sin operar al restaurante.
- **Rate limit por usuario y por IP** en `GET /consulta/{dni,ruc}/{n}`
  (20 y 60 por minuto por defecto, ADR-041). Acá lo protegido no es una
  credencial sino el **gasto**: cada consulta vale una llamada a un proveedor
  pago, así que un bucle mal escrito en una pantalla agota el plan del mes sin
  que nadie ataque nada. Por usuario **además de** por IP porque un local
  entero sale por la misma dirección: con un límite solo por IP, el primer
  cajero que se pasa deja sin consultar a los otros tres. Se cuenta después
  del permiso —un 403 no gasta cuota— y con el mismo fail-open que el login.
- Agentes de IA: usuarios `tipo=agente_ia` con permisos mínimos y
  **credencial propia** — un token de API de larga vida (`token_agente`,
  ADR-032), no un PIN. `Authorization: Bearer prv_...`; se guarda solo su
  SHA-256 y el valor en claro sale una única vez, al emitirlo. Se revoca de
  a uno (`DELETE /users/{id}/tokens/{token_id}`), sin apagar la cuenta ni
  las demás integraciones. Un usuario `humano` no puede tener token.
  Motivo: un PIN de 6 dígitos son 20 bits de entropía en un archivo de
  configuración, y el lockout que protege a una persona apagaría una
  integración.

## Auditoría y logs

- `audit_log` inmutable: quién, qué entidad, qué acción, cuándo, dónde
  (empresa, sucursal, IP), valor anterior y nuevo (JSONB).
- **Transversal** (ADR-031): escribe cualquier módulo por
  `src.shared.auditoria.registrar`, en la misma transacción que el cambio
  auditado. Hoy dejan rastro: login y login fallido, elevación de PIN de
  supervisor, alta de usuario y asignación de rol/permiso, anonimización de
  persona y de postulante, anulación de venta y descuento manual, aprobación
  de ajuste de inventario, emisión de OC, ejecución de pago a proveedor e
  ingreso/retiro de efectivo del cajón.
- Se lee por `GET /api/v1/auditoria` (permiso `auditoria.leer`, del rol
  `contador` — Contabilidad audita a Compras, Almacén y cajas, RN-CTB-009).
  **No hay endpoint de escritura**: el auditado no puede dictar lo que dice
  su auditoría. El alcance sale del JWT (ADR-004); las filas sin empresa ni
  sucursal solo las ve el superusuario.
- Tres flujos de logs: aplicación, seguridad y auditoría — formato uniforme
  (JSON en producción), correlacionados por `request_id`. Implementado
  2026-07-26; ver
  [../engineering/devops.md](../engineering/devops.md#monitoreo-y-observabilidad).
- El flujo `seguridad` registra login fallido, bloqueo de cuenta, reuso de
  refresh token (señal de token robado) y rate limit superado. El `audit_log`
  deja el rastro legal; este flujo es el que dispara alertas.
- PIN, contraseñas, tokens y cabeceras `Authorization`/`Cookie` se redactan
  antes de escribirse en un log y antes de salir hacia el reporte de errores.
  Un log es una brecha si guarda lo que la autenticación protege.

## Endurecimiento

- HTTPS obligatorio fuera de local. TLS termina en nginx/Caddy; la aplicación
  emite `Strict-Transport-Security` cuando `ENVIRONMENT=production`.
- Cabeceras en toda respuesta: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- **Content-Security-Policy**, distinta en cada punta porque protegen cosas
  distintas:
  - **API** (`src/core/app.py`): devuelve JSON y no debe cargar nada, así
    que va la más restrictiva posible —
    `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.
    Vuelve inerte cualquier respuesta que llegara a interpretarse como
    HTML. `/docs` queda exceptuado (Swagger UI carga de un CDN) y en
    producción ni existe.
  - **Frontend** (`frontend/middleware.ts`): **nonce por request** +
    `'strict-dynamic'`. Next inyecta scripts inline propios (hidratación,
    streaming RSC); sin nonce habría que admitir `'unsafe-inline'` en
    `script-src`, que anula la defensa contra XSS. `style-src` sí mantiene
    `'unsafe-inline'` — Next emite estilos críticos inline sin nonce; es la
    concesión conocida del patrón y no toca el vector de ejecución de
    script.
- **Escaneo de dependencias**: `pip-audit` en CI (informativo hoy) y
  `.github/dependabot.yml` para pip, npm, github-actions y docker — el
  primero avisa de la CVE, el segundo abre el PR que la cierra.
- `TrustedHostMiddleware` (dominios permitidos) y CORS con orígenes
  explícitos — comodines prohibidos en producción.
- `/docs` y `/openapi.json` deshabilitados en producción.
- Los endpoints de salud (`/health`, `/health/ready`, `/health/backups`) son
  públicos a propósito —un monitor externo no puede autenticarse— y por eso
  devuelven solo estados: nunca hostnames, DSN ni errores crudos. El detalle
  va al log.
- **Arranque fallido ante configuración insegura**: con
  `ENVIRONMENT=production`, un `JWT_SECRET` placeholder o corto, `DEBUG=true`,
  la contraseña de base de datos por defecto o `*` en hosts/orígenes impiden
  que la aplicación levante (`src/config/settings.py`).
- El ERP no ejecuta comandos externos ni evalúa input como código.
- Secretos SOLO en variables de entorno; jamás en repo. Custodia y rotación:
  [../engineering/devops.md](../engineering/devops.md).
- Webhooks entrantes (Izipay, Meta) validados por firma antes de tocar dominio.
- Idempotency keys en operaciones de dinero (ver
  [../engineering/api-guidelines.md](../engineering/api-guidelines.md)).

## Sitio de marca (storefront)

Charlie's Pizzas (`storefront/`) es una app Next aparte del back office, sin
JWT en su superficie pública, y con cuentas de cliente separadas de los
usuarios del ERP. Ver [ADR-103](../architecture/adr/ADR-103-el-sitio-de-marca-es-un-modulo-storefront-y-una-app-aparte.md),
[ADR-104](../architecture/adr/ADR-104-la-cuenta-del-sitio-es-una-credencial-aparte-vinculada-por-evento.md)
y [ADR-105](../architecture/adr/ADR-105-el-pedido-web-es-canal-propio-y-el-efectivo-sigue-siendo-adelantado.md).

- **Credenciales aisladas del ERP** (RN-WEB-006): la cuenta del sitio
  (`storefront_cuenta`) firma su JWT con `STOREFRONT_JWT_SECRET` (distinto de
  `JWT_SECRET`) y `aud="storefront"`. El decoder del ERP rechaza un token de
  cuenta web por firma; el decoder del sitio exige el `aud` y rechaza un
  token del ERP aunque comparta secreto por accidente de configuración —
  probado en `tests/test_storefront_aislamiento_credenciales.py` con
  secretos forjados a propósito, no solo con el valor por defecto de
  desarrollo (`jwt_secret`/`storefront_jwt_secret` comparten placeholder en
  dev/test, y un test que no fuerce secretos distintos puede pasar por la
  razón equivocada).
- **El navegador nunca habla con la API**: `storefront/lib/api.ts` es el
  único cliente, corre server-side, y solo llama a
  `/api/v1/storefront/publico/*` y `/api/v1/storefront/cuentas/*`. No hay
  proxy genérico (a diferencia de `frontend/app/api/proxy/[...ruta]`) — el
  navegador no puede pedir nada que ese archivo no haya decidido exponer
  primero.
- **Allowlist de campos, no serialización directa** (RN-WEB-001): la
  superficie pública (`src/modules/storefront/api/publico_routers.py`) nunca
  devuelve `empresa_id`/`grupo_id`, costos, datos de `persona` de terceros
  (proveedores, trabajadores), remuneración ni cantidades de receta — solo
  nombres de ingrediente, nunca cuánto lleva cada uno. Cada respuesta sale de
  un schema `*PublicoOut` enumerado; ningún endpoint público serializa un
  modelo ORM directamente. `application/sitio.py` solo llama a los
  `queries_publicas.py` de otros módulos (nunca a su dominio ni
  infraestructura), así que ampliar lo que el sitio muestra exige tocar el
  contrato público del módulo dueño, no solo el storefront.
- **Rate limit y respuesta ante extracción**: `storefront_publico`
  (120/hora por IP) y `storefront_pedidos` (20/hora por IP) reusan
  `src.core.rate_limit` — mismo mecanismo que `/auth/login`, mismo
  fail-open si Redis no responde (una caída de Redis no puede tumbar el
  sitio) y mismo flujo `seguridad` para la alerta: un scraping del catálogo
  o un bombardeo de pedidos falsos deja "Rate limit superado" en ese log,
  no en silencio.
- **Auditoría de cambios propios**: `contenido`, `fotos`, `direcciones`,
  `pedidos` y `cuentas` (perfil, alta) escriben en `audit_log` vía
  `src.shared.auditoria.registrar`, en la misma transacción que el cambio.
  Una acción de cliente (no de staff del ERP) audita con `usuario_id=None`
  y pone el id de la propia cuenta/pedido en `entidad_id` — `audit_log.usuario_id`
  es FK a `usuario.id`, que no existe para un cliente del sitio.
- **Webhook de pagos** (`POST /api/v1/storefront/webhooks/izipay`, RN-WEB-016):
  es la única escritura pública sin JWT ni token de pedido, así que lo que la
  autentica es la **firma** que verifica el adaptador (`Pasarela.
  verificar_webhook`) sobre el cuerpo crudo; sin firma válida no toca la base
  (400), y con credenciales cargadas pero adaptador sin terminar responde 501.
  Idempotente por `pago_id_externo` único. Rate limit 120/min por IP. **La
  pasarela de prueba** (sin `IZIPAY_API_KEY`) acepta como "firma" el resultado a
  simular —cualquiera podría marcar un pedido como pagado—, por eso solo existe
  fuera de producción (`settings.es_produccion`), y en producción sin
  credenciales `izipay_disponible()` corta el checkout antes de crear un
  pedido que nadie podría cobrar. Probado en `tests/test_storefront_pedidos.py`
  (`test_en_produccion_sin_credenciales_izipay_no_se_puede_usar`).
- **CSP propia** (`storefront/middleware.ts`, nonce por request,
  `'strict-dynamic'`), separada de la del ERP — el sitio no debe poder cargar
  ni ejecutar nada del back office ni viceversa.
- **Runbook de dominio productivo**: `charlies.majambo.com.pe` necesita su
  registro DNS A creado **antes** del bloque en el `Caddyfile` (Let's Encrypt
  corta el certificado a los 5 fallos) — mismo procedimiento que
  [staging.md](../engineering/staging.md). El dominio nunca va en
  `ALLOWED_HOSTS`/CORS de la API: el sitio solo la llama por
  `API_INTERNAL_URL` en la red interna de Docker, nunca desde el navegador.

## Backups

Copia de seguridad exacta de los datos y archivos del ERP y del grupo
empresarial; su función es recuperar la información original ante un
imprevisto. Automáticos, con verificación de integridad y restauración
probada.

**Frecuencia diaria, retención 30 días** (revisado 2026-07-26; antes decía
mensual e incremental — para un negocio que vende todos los días eso
implicaba perder hasta un mes de caja, y un dump completo de este ERP pesa
megas). Se almacena en una ubicación distinta a la del ERP y los datos
originales, con redundancia geográfica: una copia en infraestructura 100%
dentro de la empresa (on-premise), y otra 100% en la nube.

Un backup que nunca se restauró no es un backup: el proceso incluye una
restauración de prueba contra una base desechable, no solo la validación
del archivo. Implementación y runbook de restauración:
[../engineering/devops.md](../engineering/devops.md#backups).
