# Checklist de code review

Revisar contra `/CLAUDE.md` y los docs de `docs/`. Rechazar si falla algo de:

## Arquitectura

- [ ] Lógica de negocio en `domain/` de su módulo — no en api ni en otro módulo.
- [ ] Sin imports entre dominios de módulos (solo eventos/contratos).
- [ ] Dependencias correctas: `api → application → domain`.
- [ ] Sin abstracciones especulativas ni código duplicado/muerto.

## Seguridad

- [ ] Input validado (tipos, formato, reglas de negocio).
- [ ] Query respeta tenant y permisos RBAC.
- [ ] Sin secretos en código; sin PIN/tokens en logs.
- [ ] Idempotencia en operaciones de dinero.
- [ ] Cambios sensibles registran auditoría.

## Calidad

- [ ] Tests incluidos y pasando; linters limpios.
- [ ] Migración Alembic si cambió esquema (+ `architecture/data-model.md` actualizado).
- [ ] README del módulo, CHANGELOG y ROADMAP actualizados.
- [ ] Commit en Conventional Commits.
