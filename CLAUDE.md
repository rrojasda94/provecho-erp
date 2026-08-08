# Provecho ERP — Reglas del juego

ERP modular para grupo de restaurantes (multi-marca, multi-sucursal, una empresa).
**Provecho** = el ERP (software). **Grupo Majambo** = el grupo empresarial que lo usa.
Estas reglas son obligatorias durante todo el desarrollo.

## Arquitectura (no romper)

- **Modular Monolith** + **Clean Architecture** + **DDD** por módulo.
- **Repository Pattern** + **Unit of Work** para acceso a datos.
- **Event-driven interno**: los módulos se comunican entre sí SOLO vía eventos
  (`src/core/events.py`) o contratos públicos. Nunca importar el dominio de otro módulo.
- Cada módulo es independiente y extensible. Removerlo no toca el dominio de
  los demás, pero sí obliga a deshacer sus registros en `core`/seeder/frontend
  (no hay manifiesto ni autodescubrimiento — ver
  `docs/roadmap/deuda/transversal.md`).
- Estructura por módulo (crear capas solo al implementarlas):
  `domain/` (entidades, reglas), `application/` (casos de uso), `infrastructure/`
  (repositorios SQLAlchemy), `api/` (routers FastAPI).
- **Crear un módulo nuevo: seguir `docs/engineering/module-guide.md`** — la
  estructura se copia de `purchases`, pero activarlo son 7 registros fuera
  del módulo.

## Estructura de carpetas

```
src/
  modules/        # inventory, sales, purchases, accounting, users (+ futuros)
  shared/         # utilidades transversales sin lógica de negocio
  core/           # app factory, db, event bus, auth
  config/         # settings (pydantic-settings, lee .env)
tests/
frontend/         # Next.js + TypeScript
docs/             # arquitectura, ADRs, dominio, modelo de datos
```

## Stack

Backend: Python 3.12+ / FastAPI / SQLAlchemy / Alembic / Celery / Redis.
Frontend: Next.js / React / TypeScript. DB: PostgreSQL. Storage: S3.
Auth: JWT + refresh token, PIN hasheado con **Argon2id**. Docker para todo.

## Principios

SOLID, DRY, KISS, Clean Code, Feature First, Dependency Injection,
Composition over Inheritance. Nunca código duplicado. Nunca lógica fuera de
su dominio. Bajo acoplamiento, alta cohesión.

## Flujo de trabajo obligatorio

1. **Especificación y contratos ANTES de implementar** (README del módulo + docs).
2. Todo cambio lleva **pruebas** y **documentación actualizada** en el mismo cambio.
3. Explicar decisiones arquitectónicas cuando haya alternativas (ADR en `docs/architecture/adr/`).
4. El código pasa `ruff` (backend) y `eslint` (frontend) antes de commit.
5. Commits: **Conventional Commits**. Versionado: **SemVer**. Actualizar `CHANGELOG.md`.
6. Actualizar `ROADMAP.md` al construir algo nuevo.

## Formato

snake_case (Python), 4 espacios, UTF-8, LF, máx 100 chars/línea, una clase por
archivo, un archivo por responsabilidad, newline final. Comentarios solo cuando
el código no sea expresivo.

## Seguridad (innegociable)

- JWT + refresh, RBAC: Usuario → Rol → Permisos → Acciones → Restricciones → Sucursales → Empresa → Datos.
- Toda consulta respeta contexto de tenant (empresa/marca/sucursal).
- Validar TODO input de cliente (tipos, longitud, formato, reglas de negocio).
- Idempotencia en operaciones críticas (pagos, compras, facturación).
- Auditoría: quién, qué, cuándo, dónde, valor anterior/nuevo.
- Nunca ejecutar comandos externos arbitrarios. HTTPS en producción.

## Integraciones externas

Factiliza (facturación electrónica PE), Google API, Meta API, Izipay (ADR-003).
Siempre detrás de adaptadores en `src/shared/integrations/` — nunca llamar
APIs externas desde el dominio.

## Datos de prueba

Usuario: `admin`, PIN: `123456` (solo entornos no productivos, vía seeder).

## Referencias

- Índice de documentación: `docs/00_PROJECT.md` (agrupada por tema)
- Guía de ingeniería (principal): `docs/engineering/engineering-guide.md`
- Terminología oficial: `docs/foundation/glossary.md`
- Principios invariantes: `docs/foundation/business-philosophy.md`
- Reglas de negocio: `docs/domain/business-rules.md`
- Modelo de negocio y flujos: `docs/foundation/vision.md`, `docs/domain/workflows.md`
- Modelo de datos: `docs/architecture/data-model.md`
- Eventos entre módulos: `docs/architecture/events.md`
- Guías por área para agentes: `docs/prompts/`
- Bitácora de construcción: `ROADMAP.md`
