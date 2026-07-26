"""Exporta el contrato OpenAPI vigente a un archivo versionado en el repo.

Un cliente externo (Android, PC, integraciones) puede generar su SDK contra
este archivo sin necesitar un servidor corriendo. CI lo regenera y lo
compara contra el commiteado (`ci.yml`): si difieren, alguien cambió un
endpoint sin dejar el contrato al día — la comprobación falla en el PR que
lo causó, no cuando un cliente externo se entera por las malas.

Uso:
    python -m src.core.openapi_export
"""

import json
from pathlib import Path

from src.core.app import create_app

DESTINO = Path("docs/architecture/openapi.json")


def generar() -> dict:
    return create_app().openapi()


def escribir(destino: Path = DESTINO) -> Path:
    esquema = generar()
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Claves ordenadas + salto de línea final: el diff entre corridas refleja
    # solo cambios reales del contrato, no reordenamientos de FastAPI.
    contenido = json.dumps(esquema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    destino.write_text(contenido, encoding="utf-8", newline="\n")
    return destino


if __name__ == "__main__":
    ruta = escribir()
    print(f"Contrato OpenAPI exportado a {ruta}")
