- **La deuda técnica del ROADMAP se partió por área** (2026-08-08). Eran
  2.044 líneas en una sola sección de `ROADMAP.md` con 17 subsecciones, y era
  el otro punto donde chocaban las ramas paralelas: dos PRs de módulos
  distintos conflictuaban por compartir archivo, no por contradecirse. Ahora
  cada área vive en `docs/roadmap/deuda/<área>.md` y `ROADMAP.md` conserva un
  índice con el conteo de ⬜ abiertos y ✅ cerrados. Las referencias en prosa
  del tipo «ver ROADMAP → Deuda técnica → Frontend» siguen valiendo: el área
  es el nombre del archivo.
  - De paso se fusionó la fila **duplicada** `Módulo \`sales\` (PDV)` de la
    tabla de estado F0. Eran dos versiones parciales de la misma fila —una
    con la pantalla KDS, otra con variantes y opciones—, resultado de un
    merge anterior; ninguna contenía a la otra, así que leer la tabla daba
    una respuesta distinta según qué fila mirabas.
