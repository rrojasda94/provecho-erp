# Provecho ERP

ERP modular para grupo de restaurantes multi-marca y multi-sucursal.
Resuelve venta, fabricación, inventarios, compras, almacén, transporte,
contabilidad, RRHH y supervisión. Funciona como webapp y app Android (15+)
y soporta agentes de IA y humanos para toma de pedidos.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy, Alembic |
| Frontend | Next.js, React, TypeScript |
| Base de datos | PostgreSQL |
| Cache / Workers | Redis, Celery |
| Auth | JWT + refresh token, PIN con Argon2id, RBAC |
| Infra | Docker, GitHub Actions |
| Observabilidad | Logs JSON correlacionados, Sentry/GlitchTip, chequeos de salud |
| Integraciones | Factiliza (facturación electrónica PE) |

## Arranque local

```bash
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
docker compose exec api python -m src.seeders.seed
```

> La base de desarrollo es el contenedor `db` (Postgres 16). El `.env` guarda
> la URL vista desde el **host** (`localhost:5433`) para alembic, pytest y un
> uvicorn suelto; a los contenedores el compose les inyecta `db:5432`. Detalle
> y cómo apuntar a un Postgres externo en
> [devops.md](docs/engineering/devops.md).

> `docker-compose.yml` es **solo desarrollo** (monta el código, `--reload`,
> Postgres con contraseña de juguete). Para servidor:
> `docker-compose.prod.yml` — ver
> [devops.md](docs/engineering/devops.md#despliegue).

- API: http://localhost:8000 — docs OpenAPI en http://localhost:8000/docs
  (deshabilitadas en producción)
- Web: http://localhost:3000 — login por PIN + dashboard gerencial
  (ventas del día, stock bajo mínimo, cajas abiertas; ADR-012). Primera
  pantalla real del frontend, corriendo servidor: el JWT vive en cookie
  httpOnly, nunca en el navegador vía JS.

### Salud

| Endpoint | Qué responde |
|----------|--------------|
| `/health` | Liveness — el proceso responde |
| `/health/ready` | Readiness — base de datos, Redis, cola (503 si cae una crítica) |
| `/health/backups` | Horas desde el último backup (503 si venció) |

### Backups

```bash
python -m src.backups.backup
```

Dump, verificación, restauración de prueba, copia externa y purga. Requiere
`postgresql-client`. Programación por cron y runbook de restauración en
[docs/engineering/devops.md](docs/engineering/devops.md#backups).

### Sin Docker (backend)

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
```

### Tests y lint

```bash
pytest
ruff check .
cd frontend && npm run lint && npm run typecheck
```

## Documentación

- Reglas de desarrollo: [CLAUDE.md](CLAUDE.md)
- Índice completo: [docs/00_PROJECT.md](docs/00_PROJECT.md)
- Arquitectura: [docs/architecture/overview.md](docs/architecture/overview.md)
- Modelo de negocio: [docs/foundation/vision.md](docs/foundation/vision.md)
- Modelo de datos: [docs/architecture/data-model.md](docs/architecture/data-model.md)
- Bitácora de construcción: [ROADMAP.md](ROADMAP.md)
- Cada módulo tiene su especificación en `src/modules/<módulo>/README.md`
