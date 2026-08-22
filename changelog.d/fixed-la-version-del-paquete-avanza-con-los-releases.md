- **El paquete decía 0.1.0 con el proyecto en 0.5.0** (2026-08-22). No era
  `settings.app_version` desactualizado: `pyproject.toml` llevaba clavado en
  `0.1.0` desde el 2026-07-04, cuatro releases atrás. `cortar_version.py`
  juntaba los fragmentos en `CHANGELOG.md` y borraba `changelog.d/`, y ahí
  terminaba; la versión se teclea tres veces al cortar un release —argumento
  del script, mensaje de commit y tag— y no aterrizaba en ningún archivo salvo
  el CHANGELOG. Nadie la olvidó una vez: **no había mecanismo**.
- **Costó donde más duele para diagnosticar.** De `pyproject.toml` salen el
  `release` con el que GlitchTip agrupa los errores y la `version` que publica
  `/docs`. Cada error reportado desde julio quedó etiquetado `0.1.0`, así que
  "esto apareció en la 0.4.0" —la mitad del valor de tener reporte de
  errores— no se podía responder. El tag de la imagen sí era correcto (sale
  del tag de git), lo que hacía el desfase más difícil de notar: por fuera
  todo se veía bien versionado.
- **Ahora hay una sola fuente de verdad.** `pyproject.toml` la declara,
  `settings.app_version` la lee de la metadata del paquete instalado en vez de
  repetirla como literal, y `cortar_version.py` la sube al cortar cada
  release. Un literal duplicado era la condición para que esto pasara.
- **`tests/test_version.py` falla si se vuelven a separar**: compara
  `pyproject.toml` con la última sección con número del CHANGELOG. Verificado
  contra la deriva real — con `0.1.0` la prueba se pone roja.
- En desarrollo la versión se refresca al reinstalar (`pip install -e
  ".[dev]"`): la metadata se congela al instalar. La imagen instala desde cero
  en cada build, así que ahí no aplica.
