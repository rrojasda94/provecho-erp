- Copiar `.env.example` a `.env` —el primer paso del README— dejaba la API en
  bucle de reinicio: `ALLOWED_HOSTS=*` reventaba el arranque con
  `SettingsError`. El `.env.example` documenta «listas separadas por coma» y
  `settings.py` tenía el validador para eso, pero pydantic-settings decodifica
  como JSON todo campo de tipo complejo **antes** de que corra ningún
  validador, así que `_lista_por_comas` no se ejecutaba nunca. Se marcan
  `allowed_hosts` y `cors_origins` con `NoDecode` para que el valor llegue
  crudo al validador, que ahora también resuelve el JSON que antes resolvía
  pydantic-settings — quien ya tenía su `.env` en ese formato no se entera.
  Solo se veía al levantar `docker compose` desde un clon limpio: los tests
  corren con los valores por defecto y nunca leían un `.env`. Van seis casos
  en `tests/test_settings.py`, incluido el que congela que en producción el
  comodín `*` siga abortando el arranque: arreglar el parseo no podía ablandar
  el endurecimiento.
