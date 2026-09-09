- **`backend-postgres` se caía con "too many clients already" / "out of shared
  memory" en runners con muchos núcleos** (2026-09-09). `-n auto`
  (`pyproject.toml`) reparte un worker de pytest por núcleo; contra SQLite
  (job `backend`) cada worker es autónomo, pero `backend-postgres` los hace
  compartir un único Postgres con los límites por defecto
  (`max_connections=100`, `max_locks_per_transaction=64`) — un runner con más
  núcleos que eso agota la capacidad al dropear los schemas de test en
  paralelo. No era un fallo del código de ningún PR, sino de capacidad de CI.
  Se topa la concurrencia del job con `PYTEST_XDIST_AUTO_NUM_WORKERS=8` en vez
  de subir los límites del contenedor: mismo Postgres que corre en dev, menos
  superficie que tocar.
