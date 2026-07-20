# ADR 0002 — Stack tecnológico

- Estado: aceptado
- Fecha: 2026-07-04

## Decisión

| Capa | Elección | Razón principal |
|------|----------|-----------------|
| Backend | Python + FastAPI | Tipado con Pydantic, OpenAPI automático, ecosistema IA (agentes de pedido) |
| ORM / Migraciones | SQLAlchemy 2 + Alembic | Repository/UoW naturales, migraciones versionadas |
| Frontend | Next.js + React + TypeScript | Webapp responsive; base para PWA/Android |
| DB | PostgreSQL | Transaccional, JSONB para auditoría, maduro |
| Cache / Workers | Redis + Celery | Cache, colas de notificaciones e integraciones |
| Storage | S3 (compatible) | Archivos, comprobantes, imágenes |
| Auth | JWT + refresh, Argon2id | Estándar, stateless, PIN seguro |
| Infra | Docker + GitHub Actions | Igual en local y servidor; CI/CD |

## Pendientes (ADRs futuros)

- ~~Pasarela de pago~~: resuelto en ADR 0003 (Izipay).
- App Android 15+: PWA (TWA) vs app nativa/React Native. La API REST sirve a ambas.
- Broker de notificaciones y canales.
