"""Lectura del `audit_log` (ADR-029).

Vive en `core` por lo mismo que el dashboard: la tabla es transversal y no
tiene dueño de módulo — el rastro de una venta, de un ajuste y de un pago
se lee por la misma puerta.

Solo lectura y sin `POST`: el rastro se escribe desde el caso de uso que
hace el cambio (`src.shared.auditoria.registrar`), nunca desde el cliente.
Un endpoint de escritura convertiría la auditoría en algo que el auditado
puede dictar.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.shared import auditoria
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

LEER = "auditoria.leer"


class AuditLogOut(BaseModel):
    id: uuid.UUID
    ts: datetime
    usuario_id: uuid.UUID | None
    entidad: str
    entidad_id: uuid.UUID | None
    accion: str
    datos_antes: dict | None
    datos_despues: dict | None
    empresa_id: uuid.UUID | None
    sucursal_id: uuid.UUID | None
    ip: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=Pagina[AuditLogOut])
def listar(
    entidad: str | None = Query(None, description="Tabla auditada, ej. `venta`"),
    entidad_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = Query(None, description="Quién hizo el cambio"),
    accion: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    _=Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Rastro de cambios, del más reciente al más viejo.

    El alcance sale del JWT (ADR-004): se ven las filas de la empresa del
    usuario y las de sus sucursales. Las filas sin tenant —login, alta de
    rol, cambios globales— solo las ve el superusuario (permiso `*`): no hay
    forma de atribuirlas a una empresa sin adivinar, y adivinar acá es
    mostrarle a una empresa lo que pasó en otra. El superusuario ve todo
    aunque tenga sucursales asignadas: si no, el rastro de RBAC y de logins
    no lo podría leer nadie.
    """
    consulta = auditoria.q_listar(
        empresa_id=None if tenant.superusuario else tenant.empresa_id,
        sucursal_ids=None if tenant.superusuario else tenant.sucursal_ids,
        entidad=entidad,
        entidad_id=entidad_id,
        usuario_id=usuario_id,
        accion=accion,
        desde=desde,
        hasta=hasta,
    )
    return paginar(session, consulta, p)
