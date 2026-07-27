"""DTOs de la API de sync (ADR-009, fase 2).

El contenido del lote ascendente lo define `sales` (`LoteSyncIn`): quién
sabe qué es una venta válida es el módulo que la implementa, no `core`.
"""

from pydantic import BaseModel, Field

from src.modules.sales.api.schemas import LoteSyncIn


class PullOut(BaseModel):
    recurso: str
    filas: list[dict]
    # El hub necesita distinguir "no hay nada nuevo" de "hay más, seguí
    # pidiendo": sin esto tendría que adivinar comparando contra el límite.
    hay_mas: bool


class PushIn(BaseModel):
    sales: LoteSyncIn


class ErrorSyncOut(BaseModel):
    tipo: str
    id: str
    detalle: str


class PushOut(BaseModel):
    ventas: int = Field(description="Ventas creadas o ya existentes")
    pagos: int
    anuladas: int
    errores: list[ErrorSyncOut]


class RecursoOut(BaseModel):
    nombre: str
    campos: list[str]
    campo_marca: str
    motivo: str
