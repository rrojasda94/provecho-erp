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

## Pendiente de corte

Los fragmentos de **PCGE, estados financieros e IGV configurable** (ADR-081)
salen en **0.9.0**, no en la 0.8.2: son módulo nuevo —plan contable oficial,
Estado de Situación Financiera y de Resultados, régimen de IGV elegible— y no
un parche. La 0.8.2 se corta antes con sus propios cambios; esto va después,
en su propio corte.

## Cortar la versión

```bash
python scripts/cortar_version.py 0.3.0
git commit -am "chore(release): 0.3.0"
git tag -a v0.3.0 -m "0.3.0"
git push origin main --tags
```

El script mueve **tres** archivos: junta los fragmentos en `CHANGELOG.md` y
sube `version` en `pyproject.toml` **y** en `frontend/package.json`. Se agregó
el 2026-08-22, después de descubrir que el paquete llevaba cuatro releases
clavado en 0.1.0: la versión se tecleaba tres veces —argumento, mensaje de
commit y tag— y no aterrizaba en ningún archivo salvo el CHANGELOG. De
`pyproject.toml` salen el `release` con el que GlitchTip agrupa errores y la
versión de `/docs`, así que todo lo reportado desde julio cayó en el mismo
balde; `frontend/package.json` se sumó poco después, cuando el paquete de
demo salió etiquetado con la versión del frontend, que también se había
quedado atrás. `tests/test_version.py` vigila `pyproject.toml` contra el
CHANGELOG, y `tests/test_repo_coherencia.py` vigila que `pyproject.toml` y
`frontend/package.json` no se separen entre sí.

En desarrollo, la versión que reporta la app se refresca al reinstalar
(`pip install -e ".[dev]"`): la metadata del paquete se congela al instalar.
La imagen de Docker no tiene ese problema — instala desde cero en cada build.

El tag dispara `.github/workflows/release.yml`, que publica la imagen
etiquetada con esa versión.

[Keep a Changelog]: https://keepachangelog.com/es/1.1.0/
