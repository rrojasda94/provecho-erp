- **La versión que reporta el ERP salía de la metadata del paquete instalado,
  que en desarrollo se congela** (2026-08-30). `settings.app_version` leía
  `importlib.metadata.version("provecho")`, y en un `pip install -e .` esa
  metadata se escribe **una sola vez**: el código queda en vivo y la versión
  no. Como el `.venv` es uno solo para todos los worktrees, terminaba
  reportando la versión de la rama que estuviera abierta el día que se
  instaló — se encontró un venv en 0.6.0 con el repo en 0.9.1. No afectaba ni
  a la imagen ni a CI, que instalan de cero en cada corrida, pero sí ensuciaba
  `docs/architecture/openapi.json`: regenerarlo en local le metía esa versión
  ajena y el `git diff --exit-code` del CI fallaba sin que nadie hubiera
  tocado un endpoint. Ahora la versión sale del `pyproject.toml` del checkout
  —el archivo que `cortar_version.py` mueve— y la metadata queda de respaldo
  para la instalación no editable, donde el paquete vive en `site-packages` y
  no tiene el `pyproject.toml` al lado. El test pasa de comprobar el formato
  (`\d+\.\d+\.\d+`, que daba verde con cuatro releases de diferencia) a
  comparar contra el archivo.
