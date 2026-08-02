"""Fixtures compartidas por todo el suite.

Autouse: ningún test debe golpear una API externa real solo porque el
`.env` local tiene un token cargado (Factiliza, RUC/DNI). Los tests que sí
necesitan probar la integración fijan su propio token+mock explícitamente
(ver test_facturacion_electronica.py).
"""

import pytest

from src.config.settings import settings


@pytest.fixture(autouse=True)
def _sin_token_factiliza_por_defecto(monkeypatch):
    monkeypatch.setattr(settings, "factiliza_token", "")
