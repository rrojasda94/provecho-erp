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

## Arranque local

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000 — docs OpenAPI en http://localhost:8000/docs
- Web: http://localhost:3000

### Sin Docker (backend)

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
```

### Tests y lint

```bash
pytest
ruff check .
cd frontend && npm run lint
```

## Documentación

- Reglas de desarrollo: [CLAUDE.md](CLAUDE.md)
- Índice completo: [docs/00_PROJECT.md](docs/00_PROJECT.md)
- Arquitectura: [docs/architecture/overview.md](docs/architecture/overview.md)
- Modelo de negocio: [docs/foundation/vision.md](docs/foundation/vision.md)
- Modelo de datos: [docs/architecture/data-model.md](docs/architecture/data-model.md)
- Bitácora de construcción: [ROADMAP.md](ROADMAP.md)
- Cada módulo tiene su especificación en `src/modules/<módulo>/README.md`
