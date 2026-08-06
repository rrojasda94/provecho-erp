"""Punto de entrada del servidor (`uvicorn src.main:app`).

El chequeo de esquema vive acá y no en `create_app()` a propósito: los tests
construyen la app muchas veces contra SQLite en memoria, y meterlo en la
factoría los haría conectarse a la base real de `settings` en cada una. Acá
corre una sola vez, cuando arranca el proceso de verdad.
"""

import src.core.models_registry  # noqa: F401  (puebla `Base.metadata`)
from src.config.settings import settings
from src.core.app import create_app
from src.core.database import Base, engine
from src.core.esquema import verificar_al_arrancar

# Producción aborta; desarrollo solo avisa (ahí una migración a medio
# escribir es lo normal). Ver `src/core/esquema.py`.
verificar_al_arrancar(engine, Base.metadata, estricto=settings.es_produccion)

app = create_app()
