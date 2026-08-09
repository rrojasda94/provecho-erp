# Contribuir a Provecho ERP

Lee primero [CLAUDE.md](CLAUDE.md) — contiene las reglas obligatorias.

## Flujo

1. Rama desde `main`: `feat/<módulo>-<descripción>` o `fix/...`.
2. Especificar antes de implementar: actualizar README del módulo y docs.
3. Implementar con pruebas (unitarias + integración cuando aplique).
4. `ruff check .` y `pytest` deben pasar. Frontend: `npm run lint` y
   `npm run typecheck` (ESLint no resuelve tipos; `tsc` es lo que atrapa un
   import que ya no existe).
5. Dejar un fragmento en [`changelog.d/`](changelog.d/) —**no** editar
   `CHANGELOG.md` a mano—, y actualizar `ROADMAP.md` y la documentación
   afectada en el mismo cambio.
6. Commits en formato [Conventional Commits](https://www.conventionalcommits.org/es/):
   `feat(inventory): agregar transferencias entre almacenes`.
7. Pull request; CI debe estar en verde. No se aceptan cambios importantes sin documentación.

`main` está protegida: los seis jobs del CI son obligatorios y la rama tiene
que estar al día con `main` antes de mergear. No hay "merge igual" — el
2026-08-07 un PR entró en rojo y dejó `main` rota un día.

Si trabajas con varias ramas a la vez (o con varias sesiones de agente en
paralelo), lee [trabajo-en-paralelo.md](docs/engineering/trabajo-en-paralelo.md):
PR en borrador desde el primer commit, y quién renumera cuando dos ramas piden
el mismo ADR o la misma cabeza de Alembic.

## Dependencias

- **Un major no se mergea sin migrar el código.** Dependabot los manda
  agrupados y aparte de los menores a propósito: son trabajo propio, no un
  bump. Si el PR sube la versión y no toca una línea de código, o falta la
  migración o el major no corresponde todavía.
- Si no corresponde, no se deja el PR abierto: se cierra y la versión entra a
  `ignore` en [`.github/dependabot.yml`](.github/dependabot.yml) **con el
  motivo escrito**. Ahí están hoy TypeScript 7, ESLint 10 y
  `@tanstack/react-table` 9, cada uno con qué lo bloquea y qué lo destraba.
- Subir la imagen base del `Dockerfile` obliga a subir los `python-version:`
  de `ci.yml`. Lo vigila `tests/test_repo_coherencia.py`.

## Reglas de código

- Sin código duplicado, sin código muerto, sin variables sin usar.
- Funciones cortas, complejidad ciclomática ≤ 10.
- La lógica de negocio vive en el `domain/` de su módulo, nunca fuera.
- Módulos se comunican solo por eventos o contratos públicos.
