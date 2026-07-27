# ADR-010 — Contrato OpenAPI exportado y verificado en CI

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

El PDV va a tener tres clientes (web, Android, PC — ver ADR-009) construidos
por separado, además de integraciones futuras (Google, Meta, terceros). Hoy
el único contrato disponible es `/docs`, que exige un servidor corriendo —
nadie puede generar un SDK, validar tipos o revisar qué cambió entre dos
versiones de la API sin levantar la aplicación.

De paso, al auditar la documentación existente (`api-guidelines.md`) contra
el código real aparecieron dos afirmaciones falsas desde hace tiempo: decía
que `idempotency_key` viaja por **header**, cuando el código siempre lo pide
como **campo del body**; y que las colecciones devuelven
`{items, total, page, page_size}`, cuando los 21 endpoints de listado
existentes devuelven un array plano. Ninguna de las dos veces alguien lo
notó porque nada comparaba la doc contra el comportamiento real.

## Decisión

**Exportar el esquema OpenAPI a un archivo versionado en el repo**
(`docs/architecture/openapi.json`, `python -m src.core.openapi_export`) y
**verificarlo en CI**: el job `backend` regenera el archivo y hace
`git diff --exit-code` contra el commiteado — si alguien cambió un endpoint
sin regenerar el contrato, el PR falla ahí, no cuando un cliente externo se
entera por las malas.

Además, `TAGS_METADATA` en `src/core/app.py` describe cada tag (antes
FastAPI solo agrupaba por nombre, sin explicar qué es cada grupo), y un
test (`test_todos_los_tags_usados_tienen_descripcion`) falla si aparece un
tag nuevo sin su entrada — mismo mecanismo de "la doc no puede desalinearse
en silencio" aplicado a la metadata, no solo a las rutas.

`api-guidelines.md` se corrige para reflejar la realidad (`idempotency_key`
en el body, colecciones sin paginar) en vez de aspirar a algo que el código
nunca implementó.

## Consecuencias

- El archivo generado es determinista (claves ordenadas, salto de línea
  final) — dos corridas seguidas producen bytes idénticos, para que el
  `git diff --exit-code` de CI no marque diferencia espuria en cada PR.
- Un cliente externo (Android, integraciones) puede generar su SDK contra
  `docs/architecture/openapi.json` sin depender de que la nube esté
  arriba — importante para el equipo de Android trabajando en paralelo
  antes de que exista un entorno compartido.
- La paginación real sigue sin construirse: se documentó honestamente que
  no existe en vez de fingir que sí, y queda en deuda técnica para cuando
  una colección (candidatas: histórico de ventas, `audit_log`) lo justifique
  por volumen.
- El contrato exportado vive en `docs/architecture/`, junto a
  `data-model.md` y `events.md` — incluido en el mismo lugar que ya
  documenta la arquitectura de datos, no en un directorio aparte de "API
  docs" que hubiera que recordar mantener sincronizado con el resto.

## Alternativas descartadas

- **Solo `/docs` en vivo, sin archivo exportado** — descartada: obliga a
  cualquier consumidor externo a tener un servidor corriendo solo para leer
  el contrato, y no deja rastro versionado de qué cambió entre commits.
- **Herramienta de documentación de API alojada** (Redoc standalone,
  Stoplight, ReadMe.io) — descartada por ahora: agrega una cuenta/servicio
  externo y un paso de publicación para un equipo de un solo desarrollador;
  el archivo JSON commiteado + `/docs` autogenerado ya cubre generar SDK y
  navegar la API. Reconsiderar si el equipo crece o hay consumidores
  externos exigiendo un portal propio.
- **Anotar `responses={...}` con el detalle de cada código de error en los
  ~100 endpoints existentes** — descartado como parte de este ADR: mejora
  real la documentación por endpoint, pero es una edición mecánica grande
  sobre código ya en producción, sin bloquear nada hoy. El formato de error
  ya es consistente (`{detail}` en todo el código) y está documentado a
  nivel de guía; anotar cada endpoint individualmente queda en deuda
  técnica, a hacerse incremental cuando se toque cada router por otra razón.
