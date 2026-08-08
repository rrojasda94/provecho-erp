- **Tres coherencias entre archivos que no se importan pasan a ser tests**
  (2026-08-08, `tests/test_repo_coherencia.py`). Las tres fallaron de verdad
  el mismo día y las tres se detectaron a mano, después de mergear.
  - **Números de ADR repetidos.** Tres ramas en paralelo eligieron "el
    siguiente" contra el `main` que cada una veía; hubo que renumerar dos
    veces (029 → 031 → 032). El número lo sigue eligiendo una persona —no hay
    forma de reservarlo—, así que lo que cambia es que el choque se ve en el
    PR y no después. También se exige numeración sin huecos: un hueco casi
    siempre es un ADR renumerado a medias.
  - **ADR ausente del índice.** `docs/00_PROJECT.md` es por donde entra
    cualquiera, persona o agente; un ADR que no está listado ahí existe solo
    para quien ya sabía que existía.
  - **El Python del CI contra el de la imagen.** El PR #49 subió el
    `Dockerfile` a 3.14 y dejó los cuatro jobs de `setup-python` en 3.12: el
    job `imagen` solo comprueba que el contenedor construya y conteste
    `/health`, así que una dependencia incompatible con el intérprete nuevo
    habría llegado a producción con `main` en verde.
  - La cadena de Alembic no entra acá: el job `backend` ya falla con más de
    una cabeza.
- **Dependabot agrupa los majors aparte y deja de mandar un PR por action**
  (2026-08-08). Los majors de pip y npm van juntos y separados de los
  menores: un major es trabajo propio, no un bump, y mezclado con los menores
  se revisa con la misma vara que ellos — que es como el #37 entró sin migrar
  nada. Las actions y las imágenes pasan a grupo único: sin agrupar, los #21,
  #22, #24, #25, #35, #36 y #38 fueron siete PRs para siete líneas de YAML, y
  ese ruido es lo que hace que se mergeen sin mirar.
- **`docs/engineering/trabajo-en-paralelo.md`** (2026-08-08): cómo trabajar
  con varias ramas o sesiones a la vez sin duplicar trabajo — PR en borrador
  desde el primer commit, y quién renumera cuando dos ramas piden el mismo
  ADR o la misma cabeza de Alembic. El 2026-08-08 salieron cuatro PRs
  distintos arreglando el mismo bug (#40, #46, #47, #48) y tres se cerraron
  sin mergear: no fue un problema de código, fue de visibilidad.
