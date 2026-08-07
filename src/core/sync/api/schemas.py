"""DTOs de la API de sync (ADR-009, fase 2).

El contenido de cada lote ascendente lo define **su módulo**: quién sabe
qué es una venta válida es `sales`, y qué es una recepción válida es
`inventory`. `core` solo sabe que hay un lote por módulo y que cada uno
viaja bajo su propia clave.
"""

from pydantic import BaseModel, Field

from src.modules.inventory.api.schemas import LoteInventorySyncIn
from src.modules.sales.api.schemas import LoteSyncIn


class PullOut(BaseModel):
    recurso: str
    filas: list[dict]
    # El hub necesita distinguir "no hay nada nuevo" de "hay más, seguí
    # pidiendo": sin esto tendría que adivinar comparando contra el límite.
    hay_mas: bool


class PushIn(BaseModel):
    """Un lote por módulo, los dos opcionales.

    El motor empuja **un módulo por ciclo de watermark**, así que en la
    práctica llega uno solo — pero el contrato admite los dos para que un
    hub que acumuló de todo no tenga que hacer dos requests.
    """

    sales: LoteSyncIn | None = None
    inventory: LoteInventorySyncIn | None = None


class ErrorSyncOut(BaseModel):
    tipo: str
    id: str
    detalle: str


class PushOut(BaseModel):
    ventas: int = Field(default=0, description="Ventas creadas o ya existentes")
    pagos: int = 0
    anuladas: int = 0
    solicitudes: int = Field(default=0, description="Solicitudes de insumos")
    recepciones: int = Field(default=0, description="Transferencias recibidas")
    conteos: int = 0
    errores: list[ErrorSyncOut] = []


class RecursoOut(BaseModel):
    nombre: str
    campos: list[str]
    campo_marca: str
    motivo: str
