- **`backend-postgres` se caía con "too many clients already" / "out of shared
  memory" al crecer el esquema de la app** (2026-09-09). Cada test aísla su
  propio schema con `Base.metadata.create_all`/`DROP SCHEMA ... CASCADE`
  sobre el esquema ENTERO de la app (todos los módulos, no solo el que ese
  test ejercita) — a esta altura (18 módulos, cientos de tablas) un solo
  `DROP SCHEMA CASCADE` pide un lock por objeto, y con varios workers de
  `pytest-xdist` dropeando a la vez contra los límites de fábrica de la
  imagen `postgres:16-alpine` (`max_connections=100`,
  `max_locks_per_transaction=64`) la corrida se caía entera. No era un fallo
  de ningún PR puntual — se reprodujo igual en dos PRs sin relación entre sí
  (uno solo agrega funciones puras a `rrhh`, el otro es documentación).
  Topar la concurrencia de `pytest-xdist` (`PYTEST_XDIST_AUTO_NUM_WORKERS=8`)
  no alcanzó por sí solo. `services:` de GitHub Actions no deja pasarle
  flags de arranque a Postgres, así que el job levanta el contenedor a mano
  (`docker run`) con `max_connections=300` y `max_locks_per_transaction=256`
  en vez de los valores de fábrica.
