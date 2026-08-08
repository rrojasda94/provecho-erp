# Fragmentos de changelog

Un archivo por cambio. Al cortar una versión, `scripts/cortar_version.py` los
junta en una sección nueva de `CHANGELOG.md` y los borra.

## Por qué

`CHANGELOG.md` se editaba siempre en la misma línea: arriba de todo, bajo
`## [Unreleased]`. Dos ramas en paralelo agregando su entrada chocan **siempre**
— no porque el contenido se contradiga, sino porque comparten el punto de
inserción. El 2026-08-08, de siete PRs mergeados en una tarde, cinco
conflictuaron acá y dos lo hicieron como archivo entero.

Un archivo por cambio no tiene punto de inserción compartido: el conflicto
deja de ser posible.

## Cómo

Nombre: `<tipo>-<slug>.md`, con `tipo` ∈ `added`, `changed`, `fixed`,
`removed`, `security` (las categorías de [Keep a Changelog]). El `slug` es
libre — que se entienda de qué habla y no lo repita otra rama.

```
changelog.d/fixed-carga-error-vs-vacio.md
changelog.d/added-token-de-api-para-agentes.md
```

Contenido: los mismos bullets que irían en `CHANGELOG.md`, sin el encabezado
`### Fixed` — lo pone el script. Misma vara de siempre: qué cambió, **por qué**
y qué costo se aceptó. Un bullet que solo dice qué se tocó no sirve de nada
dentro de seis meses.

```markdown
- **Un fetch caído se dibujaba igual que "no hay datos"** (2026-08-07). El
  patrón `.catch(() => setLista([]))` estaba en cuatro lugares y convirtió un
  fallo real en algo indiagnosticable desde la pantalla.
```

## Cortar la versión

```bash
python scripts/cortar_version.py 0.3.0
git commit -am "chore(release): 0.3.0"
git tag -a v0.3.0 -m "0.3.0"
git push origin main --tags
```

El tag dispara `.github/workflows/release.yml`, que publica la imagen
etiquetada con esa versión.

[Keep a Changelog]: https://keepachangelog.com/es/1.1.0/
