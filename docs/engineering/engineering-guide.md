# Guía de ingeniería

Referencia principal para construir Provecho — humanos y agentes de IA. El
contrato operativo terso que la IA carga cada sesión es [`/CLAUDE.md`](../../CLAUDE.md),
que **resume y apunta aquí**. Esta guía es el "por qué y cómo" extenso; no se
duplica en CLAUDE.md.

## Filosofía de desarrollo

Construir lo mínimo que resuelve el problema real. Especificar antes de
implementar. Cada capacidad, agregable o removible sin romper el resto.
Principios de negocio en [../foundation/business-philosophy.md](../foundation/business-philosophy.md).

## Arquitectura y patrones obligatorios

- Modular Monolith + Clean Architecture + DDD por módulo
  ([../architecture/overview.md](../architecture/overview.md)).
- Repository Pattern + Unit of Work para datos.
- Dependencias: `api → application → domain`; `infrastructure` implementa
  interfaces del dominio. El dominio no conoce FastAPI ni SQLAlchemy.
- SOLID, DRY, KISS, Dependency Injection, Composition over Inheritance.

## Restricciones (innegociables)

- Nunca importar el dominio de otro módulo. Comunicación solo por eventos
  ([../architecture/events.md](../architecture/events.md)) o contratos públicos.
- Nunca lógica de negocio fuera del `domain/` de su módulo.
- Nunca código duplicado ni muerto. Nunca ejecutar comandos externos.
- Toda consulta respeta contexto de tenant y RBAC
  ([../security/authorization.md](../security/authorization.md)).

## Entorno local

**El `.venv` corre Python 3.12**, la misma versión que CI y que la imagen
Docker. No es un detalle de gusto: en 3.14 las anotaciones dejaron de
evaluarse de forma eager (PEP 649), así que un error de anotación que
revienta al importar en 3.12 pasa desapercibido en 3.14 — ya ocurrió una vez
(`ListaPrecioRepo`, un método `list` que pisaba el builtin dentro del cuerpo
de la clase), y se descubrió recién en CI con la suite entera caída.

```bash
py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev,backups]"
```

## Reglas para generar código

- `snake_case`, 4 espacios, UTF-8, LF, ≤100 chars, una clase por archivo.
- Pasa `ruff` (backend) y `eslint` (frontend) antes de commit.
- Usa la terminología oficial del [glosario](../foundation/glossary.md) SIEMPRE.
- Detalle de formato y linters: [coding-standards.md](coding-standards.md).

## Reglas para crear un módulo

1. Escribir `src/modules/<módulo>/README.md` (objetivo, responsabilidades,
   casos de uso, eventos, API, entidades, reglas, dependencias).
2. Registrar reglas nuevas en [../domain/business-rules.md](../domain/business-rules.md)
   y estados en [../domain/state-machines.md](../domain/state-machines.md).
3. Capas: `domain/` → `application/` → `infrastructure/` → `api/`.
4. Activar registrando router + handlers en `core`.

## Reglas para generar APIs

REST bajo `/api/v1/`, OpenAPI automático, validación total del input,
idempotencia en dinero. Detalle: [api-guidelines.md](api-guidelines.md).

## Reglas para crear eventos

Nombre `<modulo>.<hecho_en_pasado>`; documentar la fila en el catálogo ANTES de
publicar/consumir; payload aditivo; consumidores idempotentes.

## Reglas para escribir pruebas

Todo cambio de comportamiento lleva test en el mismo commit; dominio aislado,
infraestructura contra DB. Detalle: [testing.md](testing.md).

## Reglas para documentar

Doc y tests se actualizan en el mismo cambio que el comportamiento. Docstrings
en todo público. `CHANGELOG.md` y `ROADMAP.md` al día. Conventional Commits.
