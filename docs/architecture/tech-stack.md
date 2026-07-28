# Stack tecnológico

Decisión formal en [adr/ADR-002-stack-tecnologico.md](adr/ADR-002-stack-tecnologico.md).

| Capa | Elección | Razón principal |
|------|----------|-----------------|
| Backend | Python 3.12+ / FastAPI | Tipado con Pydantic, OpenAPI automático, ecosistema IA |
| ORM / Migraciones | SQLAlchemy 2 / Alembic | Repository/UoW naturales, migraciones versionadas |
| Frontend | Next.js / React / TypeScript / Tailwind / shadcn/ui (sobre Base UI) | Webapp responsive (PWA, no app nativa — ver [ADR-013](adr/ADR-013-arquitectura-frontend.md)) |
| Base de datos | PostgreSQL | Transaccional, JSONB para auditoría |
| Cache | Redis | Cache y broker de Celery |
| Workers | Celery | Colas: emisión de comprobantes (Factiliza), notificaciones, integraciones |
| Storage | S3 (compatible) | Archivos, comprobantes, imágenes |
| Auth | JWT + refresh, Argon2id | Estándar, stateless, PIN seguro |
| Infra | Docker + GitHub Actions | Tres topologías de compose (dev/prod/hub de sucursal, ver `docs/engineering/devops.md`), misma imagen; CI/CD |
| Linters | Ruff (backend), ESLint (frontend) | Ver [../engineering/coding-standards.md](../engineering/coding-standards.md) |

## Pendientes (ADR futuro)

- ~~App Android 15+: PWA (TWA) vs nativa/React Native~~: resuelto en
  [ADR-013](adr/ADR-013-arquitectura-frontend.md) (PWA/responsive). Le habla
  siempre al hub local de sucursal, nunca directo a la nube — ver
  [ADR-009](adr/ADR-009-modo-offline-pdv.md).
- Broker/canales de notificaciones.
