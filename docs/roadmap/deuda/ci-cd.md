# Deuda técnica — CI/CD (tras la implementación de 2026-07-26)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- 🔴 **El job `frontend` está en rojo y bloquea todo merge** (2026-08-07).
  `npm run lint` muere con "Converting circular structure to JSON"
  resolviendo el `.eslintrc.json` legacy bajo ESLint 9. **Empezó solo, sin
  que nadie tocara `frontend/`**: el PR #31 pasó verde unas horas antes con
  el mismo árbol, el mismo `package-lock.json` y el mismo `npm ci`.
  **Causa no identificada.** Se descartó la versión de Node: se fijó el
  runner en 24.16.0 —el patch exacto que pasa en local— y **falló igual**,
  así que el pin se revirtió en vez de dejarlo congelando una versión por
  una teoría refutada. Lo que queda en pie: falla en el runner Linux y pasa
  en Windows con todo lo demás idéntico (mismo commit, mismo lockfile,
  `npm ci` desde cero, mismo Node), así que apunta al entorno y no al
  código.
  El arreglo que **no depende de encontrar la causa** es migrar a la CLI de
  ESLint con flat config (`npx @next/codemod@canary
  next-lint-to-eslint-cli .`): saca del medio el puente legacy que revienta,
  y hay que hacerlo igual porque `next lint` está deprecado y **desaparece
  en Next 16**.
- ⬜ **Job de despliegue** (ver *Cuando haya servidor*, punto 7): hoy el despliegue es manual y documentado. Se
  escribe cuando exista el VPS — automatizar por SSH contra una máquina que
  no existe da automatización no probada (ADR-008).
- ⬜ **Imagen de producción del frontend**: su `Dockerfile` sigue siendo de
  desarrollo (`npm run dev`), sin build de producción ni multi-stage. Por eso
  `release.yml` publica solo la imagen del backend.
- ⬜ **`pip-audit` bloqueante**: hoy es informativo (`|| true`) para que un
  aviso en una dependencia transitiva no frene un arreglo urgente en caja.
  Pasar a bloqueante cuando el equipo tenga rutina de revisión.
- ⬜ **Escaneo de la imagen** (Trivy/Grype) y firma del artefacto: el
  contenido de la imagen base no se audita todavía.
- ⬜ **Entorno de staging** (ver *Cuando haya servidor*, punto 7): hoy se saltaría de CI a producción directo.
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
