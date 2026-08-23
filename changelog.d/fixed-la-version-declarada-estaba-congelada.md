- **La versión declarada llevaba tres releases congelada en `0.1.0`**
  (2026-08-09). `scripts/cortar_version.py` cortaba el `CHANGELOG.md` y
  borraba los fragmentos, pero nunca tocaba `pyproject.toml` ni
  `frontend/package.json`: con el repo en `v0.4.0`, los dos seguían diciendo
  `0.1.0` y la versión real vivía solo en el tag de git. Lo destapó el paquete
  de demo, que nombra el ZIP con lo que declara el proyecto y salió etiquetado
  con una versión de hacía un mes. Ahora el script escribe la versión en los
  dos archivos al cortar, y `tests/test_repo_coherencia.py` falla si vuelven a
  separarse entre sí.
