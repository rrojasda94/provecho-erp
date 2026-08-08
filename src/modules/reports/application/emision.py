"""Emitir un reporte a partir de un hecho del bus.

El caso de uso central del módulo. Un evento llega, se decide de qué empresa
y sucursal es, qué regla lo distribuye y a quién; se guarda la foto y una
entrega por destinatario.

**Nada de esto aborta el hecho original.** El bus despacha post-commit
(ADR-016) y el listener corre en su propia sesión: si acá falla algo, la
venta ya está confirmada y el cierre ya está registrado. Por eso todo camino
sin salida termina en una fila guardada o en un log, nunca en una excepción
que se propague.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from src.modules.reports.application import destinatarios as resolucion
from src.modules.reports.domain import catalogo, rules
from src.modules.reports.infrastructure.models import EntregaReporte, ReporteEmitido
from src.modules.reports.infrastructure.repositories import (
    ReglaRepo,
    ReporteEmitidoRepo,
)
from src.modules.users.infrastructure.models import Almacen, Sucursal

log = logging.getLogger("provecho.app")

# `reporte_emitido.titulo` es String(200). Un título más largo es un bug de
# plantilla, pero cortarlo es mejor que perder la emisión entera al insertar.
LARGO_TITULO = 200


def _uuid(valor) -> uuid.UUID | None:
    if isinstance(valor, uuid.UUID):
        return valor
    if not valor:
        return None
    try:
        return uuid.UUID(str(valor))
    except ValueError:
        return None


def _ubicar(
    session: Session, emision: catalogo.Emision, payload: dict
) -> tuple[uuid.UUID | None, uuid.UUID | None, uuid.UUID | None]:
    """`(empresa_id, sucursal_id, almacen_id)` del hecho.

    De dónde sale depende del ámbito que la emisión declara; la clave del
    payload es siempre `<ambito>_id`. Un hecho que no se puede ubicar se
    emite igual con empresa nula — y solo el superusuario lo ve, porque
    adivinarle un tenant sería mostrarle a una empresa lo que pasó en otra.
    """
    clave = _uuid(payload.get(emision.clave_ambito))
    if emision.ambito == "empresa":
        return clave, None, None
    if emision.ambito == "sucursal":
        sucursal = session.get(Sucursal, clave) if clave else None
        return (sucursal.empresa_id if sucursal else None), clave, None
    almacen = session.get(Almacen, clave) if clave else None
    if almacen is None:
        return None, None, clave
    return almacen.empresa_id, almacen.sucursal_id, clave


def emitir(
    session: Session, codigo: str, payload: dict
) -> tuple[ReporteEmitido, list[uuid.UUID]] | None:
    """Genera el reporte y sus entregas. `None` si el código no está en el
    catálogo — un evento sin emisión declarada no es un error, es un hecho
    que nadie pidió reportar.

    No hace `commit`: lo hace el listener, que es dueño de su sesión.
    """
    emision = catalogo.obtener(codigo)
    if emision is None:
        return None

    empresa_id, sucursal_id, almacen_id = _ubicar(session, emision, payload)
    datos = catalogo.proyectar(emision, payload)
    titulo = catalogo.render(emision.titulo, datos) or emision.nombre

    regla = None
    if empresa_id is not None:
        regla = rules.elegir_regla(
            ReglaRepo(session).activas_de(empresa_id, codigo), sucursal_id
        )

    repo = ReporteEmitidoRepo(session)
    reporte = repo.add(
        ReporteEmitido(
            empresa_id=empresa_id,
            sucursal_id=sucursal_id,
            codigo_emision=codigo,
            titulo=titulo[:LARGO_TITULO],
            cuerpo=catalogo.render(emision.cuerpo, datos) or None,
            nivel=regla.nivel if regla is not None else emision.nivel,
            datos=datos,
            referencia_tipo=emision.referencia_tipo or None,
            referencia_id=_uuid(payload.get(emision.clave_referencia)),
            regla_id=regla.id if regla is not None else None,
        )
    )

    if regla is None:
        # RN-REP-005: el hueco se guarda. Antes de este módulo, un aviso sin
        # regla ni destinatario era un `log.warning` que nadie leía; acá sale
        # en la matriz como lo que es, una emisión que no llega a nadie.
        log.info(
            "Reporte emitido sin regla de distribución",
            extra={"codigo": codigo, "reporte_emitido_id": str(reporte.id)},
        )
        return reporte, []

    entregas = resolucion.resolver(
        session,
        ReglaRepo(session).destinatarios(regla.id),
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        almacen_id=almacen_id,
    )
    for usuario_id, motivo in entregas:
        repo.add_entrega(
            EntregaReporte(
                reporte_emitido_id=reporte.id,
                usuario_id=usuario_id,
                # Congelado al emitir (RN-REP-004): si mañana sacan a esta
                # persona del área, la fila tiene que seguir explicando por
                # qué lo recibió.
                motivo=motivo,
                canal=regla.canal,
            )
        )
    return reporte, [usuario_id for usuario_id, _ in entregas]
