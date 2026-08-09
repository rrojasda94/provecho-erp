- **El changelog se escribe por fragmentos y `main` quedó protegida**
  (2026-08-08). Dos cosas que se rompían por la misma razón: nada obligaba a
  que un cambio llegara sano a `main`, y todos los cambios se escribían en la
  misma línea.
  - `changelog.d/`: un archivo por cambio (`<tipo>-<slug>.md`), que
    `scripts/cortar_version.py` junta en una sección nueva al cortar la
    versión. `CHANGELOG.md` deja de editarse a mano. El punto de inserción
    compartido —arriba de todo, bajo `## [Unreleased]`— era el conflicto: de
    siete PRs mergeados el 2026-08-08, cinco chocaron ahí y dos como archivo
    entero, sin que el contenido se contradijera en ninguno.
  - Lo acumulado desde el scaffold pasa a `## [0.2.0] - 2026-08-08` y se
    etiqueta `v0.2.0`, el primer tag del repositorio.
    `.github/workflows/release.yml` ya escuchaba `tags: ["v*"]` y nunca se
    había disparado. `[Unreleased]` arranca vacío.
  - **Ruleset en `main`**: PR obligatorio, los seis jobs del CI en verde y la
    rama al día antes de mergear, sin `bypass_actors`. El 2026-08-07 el PR
    #37 se mergeó con `frontend` y `e2e` en rojo y dejó `main` rota 24 h; el
    CI lo había atrapado y no había nada que impidiera el merge. Para
    saltarlo hay que desactivar el ruleset desde Settings, que es un acto
    deliberado y no un botón al lado del merge.
