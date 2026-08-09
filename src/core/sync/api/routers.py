"""Endpoints que la nube expone a los hubs de sucursal (ADR-009, fase 2).

Viven en `core` por la misma razón que `core/dashboard_router.py`: componen
contratos públicos de varios módulos y no pertenecen a ninguno.

Dos endpoints y nada más — `pull` (la nube manda su verdad hacia abajo) y
`push` (el hub reproduce lo que ocurrió durante el corte). Ambos exigen su
propio permiso y **derivan el tenant de la cuenta de servicio**, nunca de
un parámetro: un hub no puede pedir el catálogo de otra sucursal ni
escribir ventas ajenas aunque construya el request a mano.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.sync import exportador, registro
from src.core.sync.api import schemas
from src.core.sync.contratos import AlcanceHub
from src.core.sync.tiempo import a_utc
from src.modules.inventory.application import sincronizacion as inventory_sync
from src.modules.sales.application import sincronizacion as sales_sync
from src.modules.sales.application import tasks
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Sucursal, Usuario
from src.modules.users.infrastructure.repositories import UsuarioRepo

router = APIRouter(prefix="/sync", tags=["sync"])

LEER = "sync.leer"
EMPUJAR = "sync.empujar"

LIMITE_MAXIMO = 2000


def _alcance(session: Session, actor: Usuario) -> AlcanceHub:
    """Tenant del hub, leído de sus asignaciones. Exactamente una sucursal:
    un hub es de un local (ADR-009), y una cuenta con alcance más amplio
    convertiría el sync en una fuga de datos entre sucursales."""
    sucursales = UsuarioRepo(session).sucursal_ids(actor.id)
    if len(sucursales) != 1:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "la cuenta de sync debe tener exactamente una sucursal asignada",
        )
    sucursal = session.get(Sucursal, sucursales[0])
    if sucursal is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sucursal inválida")
    return AlcanceHub(empresa_id=sucursal.empresa_id, sucursal_id=sucursal.id)


@router.get("/recursos", response_model=list[schemas.RecursoOut])
def listar_recursos(_: Usuario = Depends(require_permission(LEER))):
    """El contrato de replicación, tal como está declarado en el código:
    qué entidades baja un hub y por qué necesita cada una."""
    return [
        schemas.RecursoOut(
            nombre=r.nombre,
            campos=list(r.campos),
            campo_marca=r.campo_marca,
            motivo=r.motivo,
        )
        for r in registro.RECURSOS
    ]


@router.get("/pull", response_model=schemas.PullOut)
def pull(
    recurso: str,
    desde: str | None = None,
    limite: int = Query(default=settings.sync_lote_maximo, ge=1, le=LIMITE_MAXIMO),
    actor: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Filas del recurso con `campo_marca >= desde`, acotadas a la sucursal
    de la cuenta. Sin `desde` es la carga inicial del hub."""
    descriptor = registro.obtener(recurso)
    if descriptor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"recurso '{recurso}' no replicable")
    try:
        marca = a_utc(datetime.fromisoformat(desde)) if desde else None
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "`desde` no es ISO-8601") from e

    filas = exportador.exportar(
        session, descriptor, _alcance(session, actor), marca, limite
    )
    return schemas.PullOut(recurso=recurso, filas=filas, hay_mas=len(filas) == limite)


@router.post("/push", response_model=schemas.PushOut)
def push(
    body: schemas.PushIn,
    actor: Usuario = Depends(require_permission(EMPUJAR)),
    session: Session = Depends(get_db),
):
    """Reproduce en la nube el lote que el hub acumuló durante el corte.

    No escribe filas crudas: cada ítem pasa por el caso de uso de su módulo,
    con sus validaciones, su idempotencia y sus eventos (por eso la nube
    descuenta su propio stock y prepara los comprobantes). Un ítem rechazado
    se informa y no arrastra al resto del lote.

    El cuerpo trae un lote por módulo y los dos son opcionales: el motor
    empuja de a un módulo por ciclo de watermark, así que en la práctica
    llega uno solo.
    """
    alcance = _alcance(session, actor)
    resumen: dict = {"errores": []}
    a_encolar: list = []
    for nombre, modulo in (("sales", sales_sync), ("inventory", inventory_sync)):
        lote = getattr(body, nombre)
        if lote is None:
            continue
        parcial, pendientes = modulo.aplicar(
            session, lote.model_dump(mode="json"), alcance
        )
        resumen["errores"].extend(parcial.pop("errores", []))
        resumen.update(parcial)
        a_encolar.extend(pendientes)
    session.commit()
    # Después del commit: el worker corre en otro proceso y solo ve filas
    # confirmadas. La emisión a SUNAT es siempre de la nube, nunca del hub.
    for comprobante_id in a_encolar:
        tasks.encolar(comprobante_id)
    return resumen
