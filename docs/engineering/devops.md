# DevOps

## Docker

Todo corre en Docker: `docker compose up --build` levanta db (PostgreSQL 16),
redis, api (FastAPI) y web (Next.js). Igual en local y servidor.

## Entornos

`local → development → testing → staging → production`, cada uno con su
`.env` (plantilla: `.env.example`). Variable `ENVIRONMENT` controla el modo.
Secretos nunca en el repo.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): ruff + pytest (backend),
eslint + build (frontend) en cada push/PR. CD al tener servidor destino.

## Migraciones

Solo Alembic, versionadas en `alembic/versions/`. Nunca modificar la DB a
mano en producción. `alembic upgrade head` como paso de despliegue.

## Monitoreo y observabilidad

Objetivo (implementar por fases):

- Errores reportados (Sentry o similar).
- Métricas: CPU, memoria, tiempos de respuesta, disponibilidad.
- Logs centralizados y uniformes (JSON estructurado) — aplicación,
  seguridad, auditoría.
- Trazas para optimización.

## Backups

Automáticos con verificación y restauración probada (`pg_dump` programado +
verificación de restore). Base: cada 30 días; producción definirá frecuencia mayor.
