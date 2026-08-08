# Estándares de código

Resumen operativo en `/CLAUDE.md` (se carga en cada sesión de agente).

## Principios

SOLID, DRY, KISS, Clean Code, Clean Architecture, DDD, Feature First,
Dependency Injection, Composition over Inheritance.
Nunca código duplicado. Nunca lógica fuera de su dominio. Bajo acoplamiento,
alta cohesión.

## Formato

- `snake_case` (Python); frontend sigue convención React/TS (componentes PascalCase).
- 4 espacios de indentación, UTF-8, saltos de línea LF, newline final.
- Máximo 100 caracteres por línea.
- Una clase por archivo, un archivo por responsabilidad.
- Comillas consistentes por lenguaje (dobles en Python — default de Ruff).
- Comentarios solo cuando el código no es expresivo; nunca redundantes.

## Linters (bloquean commit y CI)

- **Ruff**: `E, F, I, UP, B, C901` — sin variables sin usar, sin código
  muerto, complejidad ciclomática ≤ 10, imports ordenados. Config en `pyproject.toml`.
- **ESLint**: `next/core-web-vitals` + `next/typescript`, `no-unused-vars`,
  `complexity ≤ 10`. Config en `frontend/eslint.config.mjs` (flat config).
- **`tsc --noEmit`** (`npm run typecheck`): ESLint no resuelve tipos, así que
  un import que la librería ya no exporta le pasa por al lado. `next build`
  sí typechequea, pero recién al final y después de empaquetar; este paso da
  la misma verdad en segundos. Bloqueante en CI.
- Formatter: ejecutar al guardar (IDE), antes de commit y en CI.

## Versionado y commits

- **SemVer** para releases; `CHANGELOG.md` actualizado en cada cambio relevante.
- **Conventional Commits**: `feat(inventory): agregar transferencias`,
  `fix(sales): ...`, `docs: ...`.

## Documentación

- Docstrings en toda clase/función/método público.
- OpenAPI se genera automático desde FastAPI y debe reflejar el código siempre.
- Todo cambio de comportamiento actualiza docs y tests en el mismo cambio.
- Ejemplos en docs deben ser funcionales y estar sincronizados con el código.
