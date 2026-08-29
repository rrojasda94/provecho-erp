# Imagen de Superset con el driver de Postgres (ADR-083 Fase C).
#
# La imagen oficial `apache/superset` en su tag "lean" (sin sufijo `-dev` —
# el que corresponde a producción, los `-dev` traen un devserver que no se
# usa acá) NO trae `psycopg2`. Comprobado al ensayar esta fase:
# `superset db upgrade` contra la Postgres de staging fallaba con
# `ModuleNotFoundError: No module named 'psycopg2'`. La documentación
# oficial resuelve esto con un `requirements-local.txt` que el entrypoint
# instala en cada arranque; se prefiere una imagen propia — determinista y
# sin depender de que el droplet tenga salida a internet cada vez que el
# contenedor arranca.
FROM apache/superset:6.1.0

USER root
# Ni `pip` a secas (cae en `/usr/local/bin/pip`, el Python del sistema) ni
# `/app/.venv/bin/pip` (ese venv no tiene `pip` instalado — es la imagen
# "lean") sirven acá: Superset corre desde ese venv, así que ahí es donde
# tiene que quedar el driver. Comprobado a mano, las dos formas fallan
# distinto: la primera "funciona" pero instala en el lugar que nadie usa; la
# segunda ni siquiera encuentra el binario. `uv` sí viene en la imagen y
# apunta al intérprete que se le diga.
RUN uv pip install --python /app/.venv/bin/python psycopg2-binary
USER superset
