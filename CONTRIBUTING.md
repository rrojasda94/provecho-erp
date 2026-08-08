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

## Reglas de código

- Sin código duplicado, sin código muerto, sin variables sin usar.
- Funciones cortas, complejidad ciclomática ≤ 10.
- La lógica de negocio vive en el `domain/` de su módulo, nunca fuera.
- Módulos se comunican solo por eventos o contratos públicos.
