# Stack tecnológico

Decisión formal en [adr/ADR-002-stack-tecnologico.md](adr/ADR-002-stack-tecnologico.md).

| Capa | Elección | Razón principal |
|------|----------|-----------------|
| Backend | Python 3.12+ / FastAPI | Tipado con Pydantic, OpenAPI automático, ecosistema IA |
| ORM / Migraciones | SQLAlchemy 2 / Alembic | Repository/UoW naturales, migraciones versionadas |
| Frontend | Next.js / React / TypeScript | Webapp responsive; base para PWA/Android |
| Base de datos | PostgreSQL | Transaccional, JSONB para auditoría |
| Cache | Redis | Cache y broker de Celery |
| Workers | Celery | Colas: emisión de comprobantes (Factiliza), notificaciones, integraciones |
| Storage | S3 (compatible) | Archivos, comprobantes, imágenes |
| Auth | JWT + refresh, Argon2id | Estándar, stateless, PIN seguro |
| Infra | Docker + GitHub Actions | Igual en local y servidor; CI/CD |
| Linters | Ruff (backend), ESLint (frontend) | Ver [../engineering/coding-standards.md](../engineering/coding-standards.md) |

## Pendientes (ADR futuro)

- App Android 15+: PWA (TWA) vs nativa/React Native. La API REST sirve a ambas.
- Broker/canales de notificaciones.
