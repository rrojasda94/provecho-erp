- **Cortar una versión ya no rompe el CI.** `openapi.json` lleva la versión
  adentro (`info.version`) y `cortar_version.py` no lo regeneraba, así que el
  archivo commiteado seguía diciendo la anterior y el job `backend` fallaba
  con un diff de una línea. Pasó en el corte de 0.7.0.

  No se veía venir en local: `settings.app_version` sale de la metadata del
  **paquete instalado**, que en un entorno editable dice la versión con la que
  se instaló hasta que alguien reinstala. En el CI la instalación es limpia,
  así que ahí sí cambia — la misma rama pasaba en local y fallaba en CI.

  Dos arreglos, uno por cada mitad del problema:

  - `cortar_version.py` **regenera el contrato** después de sellar la versión,
    forzándola por `APP_VERSION` en vez de confiar en la metadata: lo que vale
    es la versión que se acaba de sellar, no la que quedó instalada.
  - `test_el_archivo_commiteado_esta_al_dia` deja de comparar `info.version`
    —no es un endpoint, y su desfase es un artefacto del entorno— y aparece
    `test_la_version_del_contrato_es_la_del_proyecto`, que la lee de
    `pyproject.toml` y por eso dice lo mismo en los dos lados.
