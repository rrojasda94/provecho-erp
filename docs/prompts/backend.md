# Contexto para trabajar en backend

Leer antes de tocar código:

1. `/CLAUDE.md` — reglas obligatorias.
2. [engineering/engineering-guide.md](../engineering/engineering-guide.md) — guía principal.
3. [architecture/overview.md](../architecture/overview.md) — capas y dependencias.
4. [architecture/data-model.md](../architecture/data-model.md) — modelo de datos.
5. [domain/business-rules.md](../domain/business-rules.md) y [foundation/glossary.md](../foundation/glossary.md).
6. README del módulo afectado (`src/modules/<módulo>/README.md`).

## Reglas duras

- Especificar en el README del módulo ANTES de implementar.
- Usar la terminología oficial del glosario SIEMPRE.
- `api → application → domain`; infraestructura implementa interfaces del dominio.
- Comunicación entre módulos solo por eventos (`src/core/events.py`, documentados
  en [architecture/events.md](../architecture/events.md)) o contratos públicos.
- Repository + Unit of Work; el dominio no importa SQLAlchemy ni FastAPI.
- Validar todo input (Pydantic + dominio). Idempotencia en dinero.

## Checklist antes de terminar

- [ ] Tests nuevos pasan (`pytest`) y `ruff check .` limpio.
- [ ] Migración Alembic si cambió el esquema.
- [ ] Reglas nuevas en `domain/business-rules.md`, estados en `domain/state-machines.md`,
      eventos nuevos en `architecture/events.md`.
- [ ] README del módulo, `CHANGELOG.md` y `ROADMAP.md` actualizados.
- [ ] Docstrings en público nuevo; sin código duplicado ni muerto.
