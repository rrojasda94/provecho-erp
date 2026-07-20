# DevOps

## Docker

Todo corre en Docker: `docker compose up --build` levanta db (PostgreSQL 16),
redis, api (FastAPI) y web (Next.js). Igual en local y servidor.

## Base de datos: Postgres en Supabase (desarrollo)

Desde 2026-07-20 el `DATABASE_URL` de desarrollo apunta a un proyecto
**Supabase** (Postgres gestionado) en vez del contenedor `db` local —
decisión del usuario para tener la BD visualizable (Table Editor) y
disponible en línea de cara al despliegue futuro. Nada del código cambia:
Supabase es Postgres real, Alembic corre igual.

**Límite explícito — no usar Supabase Auth ni RLS todavía:**
`users` (JWT + PIN + Argon2id + RBAC) sigue siendo la única fuente de
autenticación/autorización, y el aislamiento de tenant sigue por filtro de
aplicación (ADR-004, `empresa_id` obligatorio) — no por Row-Level Security
de Postgres. Activar Auth/RLS de Supabase encima crearía dos sistemas de
permisos compitiendo. Si en el futuro se evalúa RLS como refuerzo, es una
decisión aparte que actualiza ADR-004, no una consecuencia automática de
usar Supabase como hosting.

Connection string vive solo en `.env` (nunca en el repo — ver
`.env.example` para el formato, con el contenedor `db` local como
default documentado).

## Docker local (contenedor `db`) — sigue disponible

El servicio `db` de `docker-compose.yml` sigue existiendo para trabajar
sin conexión a internet o en CI; puerto de host **5433** (el 5432 local
lo ocupa la plataforma de Charlie's Pizzas — ver comentario en
`docker-compose.yml`). Cambiar `DATABASE_URL` en `.env` alterna entre
Supabase y el contenedor local.

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
