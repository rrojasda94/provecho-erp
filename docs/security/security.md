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
