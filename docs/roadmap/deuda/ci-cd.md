# Deuda técnica — CI/CD (tras la implementación de 2026-07-26)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ⬜ **Job de despliegue** (ver *Cuando haya servidor*, punto 7): hoy el despliegue es manual y documentado. Se
  escribe cuando exista el VPS — automatizar por SSH contra una máquina que
  no existe da automatización no probada (ADR-008).
- ⬜ **`pip-audit` bloqueante**: hoy es informativo (`|| true`) para que un
  aviso en una dependencia transitiva no frene un arreglo urgente en caja.
  Pasar a bloqueante cuando el equipo tenga rutina de revisión.
- ⬜ **Escaneo de la imagen** (Trivy/Grype) y firma del artefacto: el
  contenido de la imagen base no se audita todavía.
- ⬜ **Entorno de staging** (ver *Cuando haya servidor*, punto 7): hoy se saltaría de CI a producción directo.
- ⬜ **El job `uso` no avisa cuando se rompe** (2026-08-15, ADR-047): tiene
  `continue-on-error: true`, así que un recorrido que empieza a fallar de
  verdad se ve **solo mirando el artefacto**. Es el costo aceptado de que no
  bloquee un merge, no un olvido — pero el costo existe. La salida no es
  volverlo requerido (eso cambiaría la decisión de ADR-047) sino que avise sin
  bloquear: un comentario en el PR cuando pasa de verde a rojo, o un resumen
  con las capturas. Se escribe cuando la suite tenga recorridos de verdad y se
  sepa cuánto ruido genera; con una sola spec de humo, medirlo no diría nada.
  Si para entonces nadie mira el artefacto, la respuesta correcta es borrar la
  suite, no ascenderla.
- ✅ 2026-08-15 **El job `frontend` volvió a verde** (estaba anotado en rojo
  desde el 2026-08-07). Lo cerró el PR #33 (`339a634`, 2026-08-07), que era
  exactamente el arreglo que esta ficha proponía: migrar a la CLI de ESLint
  con flat config. Nadie lo marcó y la ficha quedó ocho días describiendo un
  estado que ya no existía. Evidencia hoy: `frontend/eslint.config.mjs`
  existe, `.eslintrc.json` fue borrado en ese mismo commit,
  `frontend/package.json` dice `"lint": "eslint ."` —ya no `next lint`, que
  desaparece en Next 16— y `npm run lint` termina con **0 errores** (37
  advertencias, ninguna bloqueante). El job es además uno de los seis
  requeridos por el ruleset de `main`, así que ningún PR desde entonces
  —#66, #68, #69, #70— podría haberse mergeado con él en rojo.
- ✅ 2026-08-15 **Imagen de producción del frontend**, cerrada por el PR #69
  (`79b321a`, 2026-08-12) y no marcada. `frontend/Dockerfile` es multi-stage
  con etapa `runner`: `deps` → `builder` (`npm run build`) → `runner` sobre
  `.next/standalone`, con usuario sin privilegios, `HEALTHCHECK` contra
  `/login` y `CMD ["node", "server.js"]` — ya no `npm run dev`.
  `release.yml` publica la imagen `-web` con `target: runner` y los mismos
  tags que la del backend, y el job `imagen` de `ci.yml` la construye y la
  arranca en cada PR.
- ✅ 2026-08-08 **`tsc --noEmit` bloqueante en el job `frontend`**, y
  `main` de vuelta en verde. El PR #37 (dependabot subiendo
  `@tanstack/react-table` de 8 a 9 sin migrar nada) rompió las 13 pantallas
  que usan `tabla-datos.tsx` —en v9 no existe `useReactTable`— y **se
  mergeó con el CI en rojo**: falló en el PR (run `31202169287`) y volvió a
  fallar en `main` (`31210826670`), jobs `frontend` y `e2e`. `main` quedó
  rojo desde el 2026-08-07. Se repinea en `^8.21.3` (ver Frontend).
  Lo que el CI sí tenía y no tenía:
  - `npm run lint` pasó. ESLint no resuelve tipos: revisa el árbol
    sintáctico, no si el símbolo importado existe.
  - `npm run build` **sí** typechequea —Next 16 corre el `tsc` del proyecto,
    "Running TypeScript…", con el mismo `tsconfig.json`—, pero acá ni llegó:
    murió antes empaquetando, con `Export useReactTable doesn't exist in
    target module` de Turbopack, y arrastró al `e2e` detrás.
  - `npm run typecheck` no agrega cobertura sobre el build: agrega momento y
    claridad. Corre antes de `npm test` y del build, tarda 6 s contra ~40 s,
    y falla diciendo "tipos" en vez de un stack del bundler. Y queda de red
    si alguna vez se toca `typescript.ignoreBuildErrors`.
- ✅ 2026-07-28 **Migraciones con vuelta atrás probada**: el job `migraciones`
  de `.github/workflows/ci.yml` corre `alembic downgrade base` y vuelve a
  subir contra un Postgres 16 real en cada push y PR, así que el camino de
  regreso se ejercita antes de que haga falta revertir un despliegue.
