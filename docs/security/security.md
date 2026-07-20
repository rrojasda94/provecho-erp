# Seguridad

Autenticación, endurecimiento, auditoría y backups. El control de acceso
(roles, permisos, restricciones por tenant) vive aparte en
[authorization.md](authorization.md).

## Autenticación

- Login con username + PIN (6 dígitos) → **JWT** access (15 min) +
  **refresh token** (7 días, rotativo; reuso de token viejo revoca la cadena).
- PIN hasheado con **Argon2id**. Nunca en logs ni respuestas.
- Bloqueo tras 5 intentos fallidos (ventana 15 min).
- Agentes de IA: usuarios `tipo=agente_ia` con credenciales propias y
  permisos mínimos.

## Auditoría y logs

- `audit_log` inmutable: quién, qué entidad, qué acción, cuándo, dónde
  (sucursal, IP), valor anterior y nuevo (JSONB).
- Tres flujos de logs: aplicación, seguridad y auditoría — formato uniforme,
  centralizados (ver [../engineering/devops.md](../engineering/devops.md)).

## Endurecimiento

- HTTPS obligatorio fuera de local.
- El ERP no ejecuta comandos externos ni evalúa input como código.
- Secretos SOLO en variables de entorno; jamás en repo.
- Webhooks entrantes (Izipay, Meta) validados por firma antes de tocar dominio.
- Idempotency keys en operaciones de dinero (ver
  [../engineering/api-guidelines.md](../engineering/api-guidelines.md)).

## Backups

Copia de seguridad exacta de los datos y archivos del ERP y del grupo
empresarial; su función es recuperar la información original ante un
imprevisto. Automáticos, con verificación de integridad y restauración
probada.

Frecuencia base mensual (ajustable por entorno; producción requerirá
más), incremental — cada backup suma los datos generados en ese rango al
backup anterior. Se almacena en una ubicación distinta a la del ERP y los
datos originales, con redundancia geográfica: una copia en infraestructura
100% dentro de la empresa (on-premise), y otra 100% en la nube.
