# Seguridad

Autenticación, endurecimiento, auditoría y backups. El control de acceso
(roles, permisos, restricciones por tenant) vive aparte en
[authorization.md](authorization.md).

## Autenticación

- Login con username + PIN (6 dígitos) → **JWT** access (15 min) +
  **refresh token** (7 días, rotativo; reuso de token viejo revoca la cadena).
- PIN hasheado con **Argon2id**. Nunca en logs ni respuestas.
- Bloqueo tras 5 intentos fallidos (ventana 15 min) — protege **una cuenta**.
- **Rate limit por IP** en `/auth/login` y `/auth/refresh` (contador en Redis,
  10 intentos por minuto por defecto) — protege el **endpoint**: el lockout
  por cuenta no frena a quien rota usernames desde una misma IP. Si Redis no
  responde el límite se desactiva (fail-open) y se registra advertencia: una
  caída de Redis no puede dejar sin operar al restaurante.
- Agentes de IA: usuarios `tipo=agente_ia` con credenciales propias y
  permisos mínimos.

## Auditoría y logs

- `audit_log` inmutable: quién, qué entidad, qué acción, cuándo, dónde
  (sucursal, IP), valor anterior y nuevo (JSONB).
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
