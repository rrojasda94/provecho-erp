# Deuda técnica — Backups (tras la implementación de 2026-07-26)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ✅ 2026-07-26 **Alerta ante fallo**: el comando reporta a Sentry
  (`iniciar_sentry("backups")` + `reportar`) cuando falla, y
  `GET /health/backups` devuelve 503 cuando el último backup pasó las 26 h —
  que cubre el caso traicionero, el backup que **nunca corrió** y por eso no
  genera ningún evento de error. Falta solo dar de alta la sonda en el
  monitor externo (ver Observabilidad y salud).
- ⬜ **Restauración probada sin base desechable**: hoy `BACKUP_VERIFY_DATABASE_URL`
  es opcional y, si falta, solo se valida el archivo. Levantar la base de
  verificación en el servidor de producción para que la prueba real corra
  siempre (al menos semanal).
- ⬜ **Copia on-premise** (ver *Cuando haya servidor*, punto 4): `security.md` declara redundancia on-premise +
  nube; hoy están el disco del servidor y S3 (ambos "nube" si el servidor es
  un VPS). Falta definir dónde vive la copia dentro de la empresa.
- ⬜ **Backup de archivos de S3** (`archivo`): solo se respalda Postgres.
  Cuando el módulo de archivos exista, sus objetos también necesitan copia.
- ⬜ **Cifrado del dump en reposo**: el archivo contiene datos personales de
  trabajadores y clientes (Ley 29733). Hoy va en claro al disco y al bucket.
