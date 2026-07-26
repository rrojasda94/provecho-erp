# ADR-007 — Backups por `pg_dump` + cron, y salud expuesta a un monitor externo

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

El ERP no tenía copias de seguridad de ningún tipo, y la documentación
declaraba una política ("mensual e incremental") que para un negocio que
vende todos los días implicaba perder hasta un mes de caja.

En paralelo, no había forma de saber si el sistema estaba vivo: `/health`
devolvía `ok` mientras el proceso respondiera, aunque la base de datos
estuviera caída.

## Decisión

**Backups:** un comando (`python -m src.backups.backup`) que encadena dump →
verificación → restauración de prueba → copia externa → purga, disparado por
**cron del host**. Diarios, retención 30 días, dump completo.

**Salud:** el ERP **no envía alertas por su cuenta**. Expone su estado en
tres endpoints y deja que un monitor externo (healthchecks.io, UptimeRobot,
Uptime Kuma) haga el aviso:

| Endpoint | Qué responde | 503 cuando |
|----------|--------------|------------|
| `/health` | liveness — el proceso responde | nunca |
| `/health/ready` | readiness — base de datos, Redis, cola | cae una dependencia crítica |
| `/health/backups` | frescura del último backup | pasaron más de 26 h |

## Consecuencias

- **La verificación no es opcional.** Un backup que nunca se restauró no es
  un backup: el comando valida la firma del archivo y sus tablas críticas
  siempre, y restaura de verdad contra una base desechable si
  `BACKUP_VERIFY_DATABASE_URL` está configurada. Se niega a restaurar sobre
  la base de origen, porque `pg_restore --clean` borra el esquema destino.
- **La purga nunca borra la copia más reciente**, aunque esté vencida: si el
  cron llevaba meses caído, aplicar la retención al pie de la letra dejaría
  al ERP sin ninguna copia.
- `boto3` es dependencia **opcional** (`[backups]`), al revés que
  `sentry-sdk` (ver ADR-006): solo el host que corre el cron la necesita, así
  que la imagen de la API no la carga.
- Los backups **no** entran en el readiness. Que falte un backup es grave,
  pero devolver 503 por eso sacaría la API de rotación y dejaría al
  restaurante sin vender. Van en su propio endpoint.
- Los endpoints de salud son públicos (un monitor externo no puede
  loguearse), así que devuelven estados y nunca hostnames, DSN ni errores
  crudos. El detalle va al log.
- Umbral de 26 h y no 24: deja margen para que el cron diario corra sin
  disparar falsa alarma.

## Alternativas descartadas

- **Backup incremental** — descartado: el dump completo de este ERP pesa
  megas. Lo incremental no ahorra nada apreciable y complica justo el momento
  en que menos se quiere complejidad, que es la restauración.
- **Celery beat como planificador** — descartado: el backup tiene que correr
  precisamente cuando la aplicación está caída, que es cuando más falta hace.
  Si el worker o el broker fallan, no corre y nadie se entera. `cron` es
  independiente del ciclo de vida de la aplicación.
- **Depender solo de los backups automáticos de Supabase** — descartado como
  única copia: ata la recuperación al proveedor y al plan contratado, y no
  cubre la migración a un Postgres propio, ya prevista. Sirven como capa
  extra, no como la única.
- **Construir alertas dentro del ERP** — descartado: un sistema de alertas
  que vive en el servidor que monitorea deja de avisar exactamente cuando ese
  servidor cae. El monitor tiene que estar afuera.
- **Health check profundo en `/health`** (liveness) — descartado: si liveness
  fallara por la base de datos, el orquestador reiniciaría en bucle un
  proceso perfectamente sano. Por eso liveness y readiness están separados.
