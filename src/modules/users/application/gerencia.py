"""Parámetros operativos por empresa (`parametro_empresa`, en `shared` —
entidad transversal, no propiedad de `users`). Vive aquí porque `users` ya es
el hogar de facto de lo administrativo/transversal (mismo criterio que
`persona`).

El área propone desde su módulo; Gerencia acepta / rechaza / modifica. Hasta
que Gerencia aprueba, el módulo sigue leyendo el valor anterior (RN-GER-009).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.modules.inventory.application import queries_publicas as inventory_publicas
from src.modules.users.application.errors import Conflicto, NoEncontrado
from src.shared import magnitudes
from src.shared.magnitudes import MagnitudInvalida, Unidad
from src.shared.models import ParametroEmpresa
from src.shared.repositories import DivisaRepo, ParametroEmpresaRepo


def proponer_parametro(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    modulo: str,
    codigo: str,
    valor: dict,
    propuesto_por_id: uuid.UUID,
    motivo: str | None = None,
) -> ParametroEmpresa:
    valor, display = _canonizar(session, valor)
    return ParametroEmpresaRepo(session).add(
        ParametroEmpresa(
            empresa_id=empresa_id,
            modulo=modulo,
            codigo=codigo,
            valor=valor,
            valor_display=display,
            estado="propuesto",
            propuesto_por_id=propuesto_por_id,
            motivo=motivo,
        )
    )


def _canonizar(session: Session, valor: dict) -> tuple[dict, str | None]:
    """Resuelve la unidad que el valor declara y redondea con SUS decimales.
    Un monto sin divisa o una cantidad sin UdM no llegan a la bandeja de
    Gerencia (RN-GER-010)."""
    return magnitudes.canonizar(valor, _resolver_unidad(session, valor))


def _resolver_unidad(session: Session, valor: dict) -> Unidad | None:
    requerida = magnitudes.unidad_requerida(valor)
    if requerida is None:
        return None
    if requerida == "divisa":
        codigo = valor["divisa"]
        divisa = DivisaRepo(session).get_por_codigo(codigo)
        if divisa is None:
            raise MagnitudInvalida(f"divisa desconocida o inactiva: {codigo!r}")
        return Unidad(divisa.decimales, divisa.simbolo, prefija=True)

    # UdM vive en `inventory`: se lee por su contrato público, nunca importando
    # su dominio.
    try:
        udm_id = uuid.UUID(str(valor["unidad_medida_id"]))
    except ValueError as e:
        raise MagnitudInvalida(
            f"unidad_medida_id no es un UUID: {valor['unidad_medida_id']!r}"
        ) from e
    udm = inventory_publicas.unidad_medida_para_magnitud(session, udm_id)
    if udm is None:
        raise MagnitudInvalida(f"unidad de medida desconocida: {udm_id}")
    return Unidad(udm["decimales"], udm["nombre"], prefija=False)


def aprobar_parametro(
    session: Session,
    parametro_id: uuid.UUID,
    *,
    resuelto_por_id: uuid.UUID,
    valor: dict | None = None,
) -> ParametroEmpresa:
    """Aprueba la propuesta. `valor` no nulo = Gerencia modifica antes de
    aprobar (la tercera opción de la sección de aprobaciones)."""
    repo = ParametroEmpresaRepo(session)
    propuesta = _propuesta(repo, parametro_id)
    anterior = repo.get_vigente(propuesta.empresa_id, propuesta.modulo, propuesta.codigo)
    if anterior is not None:
        anterior.estado = "reemplazado"
        session.flush()  # libera el índice único parcial antes de marcar la nueva
    if valor is not None:
        # Gerencia modifica: el valor corregido se valida y redondea igual que
        # el propuesto — nadie mete un monto sin divisa por la puerta de atrás.
        propuesta.valor, propuesta.valor_display = _canonizar(session, valor)
    propuesta.estado = "vigente"
    propuesta.resuelto_por_id = resuelto_por_id
    propuesta.resuelto_en = datetime.now(UTC)
    return propuesta


def rechazar_parametro(
    session: Session,
    parametro_id: uuid.UUID,
    *,
    resuelto_por_id: uuid.UUID,
    motivo_rechazo: str,
) -> ParametroEmpresa:
    propuesta = _propuesta(ParametroEmpresaRepo(session), parametro_id)
    propuesta.estado = "rechazado"
    propuesta.motivo_rechazo = motivo_rechazo
    propuesta.resuelto_por_id = resuelto_por_id
    propuesta.resuelto_en = datetime.now(UTC)
    return propuesta


def listar_parametros(
    session: Session,
    empresa_id: uuid.UUID | None = None,
    estado: str | None = None,
    modulo: str | None = None,
) -> list[ParametroEmpresa]:
    return ParametroEmpresaRepo(session).list(empresa_id, estado, modulo)


def _propuesta(repo: ParametroEmpresaRepo, parametro_id: uuid.UUID) -> ParametroEmpresa:
    parametro = repo.get(parametro_id)
    if parametro is None:
        raise NoEncontrado("parámetro no encontrado")
    if parametro.estado != "propuesto":
        raise Conflicto(f"el parámetro ya fue resuelto ({parametro.estado})")
    return parametro
