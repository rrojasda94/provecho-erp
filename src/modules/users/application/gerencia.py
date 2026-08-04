"""Parámetros operativos por empresa (`parametro_empresa`, en `shared` —
entidad transversal, no propiedad de `users`). Vive aquí porque `users` ya es
el hogar de facto de lo administrativo/transversal (mismo criterio que
`persona`).

El área propone desde su módulo; Gerencia acepta / rechaza / modifica. Hasta
que Gerencia aprueba, el módulo sigue leyendo el valor anterior (RN-GER-009).
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from src.modules.inventory.application.queries_publicas import (
    unidad_medida_para_magnitud,
)
from src.modules.users.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
)
from src.shared import magnitudes, parametros
from src.shared.magnitudes import MagnitudInvalida, Unidad
from src.shared.models import DecisionGerencial, Divisa, ParametroEmpresa
from src.shared.models.decision_gerencial import RESULTADOS, TIPOS
from src.shared.repositories import (
    DecisionGerencialRepo,
    DivisaRepo,
    ParametroEmpresaRepo,
)


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
    udm = unidad_medida_para_magnitud(session, udm_id)
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


# --- Divisas (RN-GER-010: decimales configurables por moneda, no una
# constante del código) -------------------------------------------------
def crear_divisa(
    session: Session, *, codigo: str, nombre: str, simbolo: str, decimales: int
) -> Divisa:
    repo = DivisaRepo(session)
    if repo.get_por_codigo(codigo) is not None:
        raise Conflicto(f"ya existe una divisa activa con código {codigo!r}")
    return repo.add(
        Divisa(codigo=codigo, nombre=nombre, simbolo=simbolo, decimales=decimales)
    )


def editar_divisa(session: Session, divisa_id: uuid.UUID, **campos) -> Divisa:
    repo = DivisaRepo(session)
    divisa = repo.get(divisa_id)
    if divisa is None:
        raise NoEncontrado("divisa no encontrada")
    for campo in ("nombre", "simbolo", "decimales", "activa"):
        if campo in campos and campos[campo] is not None:
            setattr(divisa, campo, campos[campo])
    return divisa


def listar_divisas(session: Session) -> list[Divisa]:
    return DivisaRepo(session).list()


# --- Acta de decisión gerencial (RN-GER-002) ----------------------------
def registrar_decision(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    tipo: str,
    referencia_tipo: str,
    referencia_id: uuid.UUID,
    decidido_por_id: uuid.UUID,
    sustento: str,
    resultado: str,
    fecha: date,
    condiciones: str | None = None,
    ejecuta_area: str | None = None,
    archivo_id: uuid.UUID | None = None,
) -> DecisionGerencial:
    """Materializa el acta: una decisión verbal no tiene validez operativa.

    `referencia_tipo`/`referencia_id` apuntan a lo decidido sin FK — la
    decisión aplica a una OC, una campaña o una sanción, y ninguna de esas
    tablas puede ganar una FK hacia `shared` (ver el modelo).
    """
    if tipo not in TIPOS:
        raise ReglaNegocio(f"tipo de decisión inválido: {tipo}")
    if resultado not in RESULTADOS:
        raise ReglaNegocio(f"resultado de decisión inválido: {resultado}")
    if not (sustento or "").strip():
        raise ReglaNegocio("la decisión necesita sustento (RN-GER-002)")
    # Aprobar "con condiciones" sin decir cuáles deja al área ejecutora sin
    # saber qué cumplir: el acta no sirve para nada.
    if resultado == "aprobado_con_condiciones" and not (condiciones or "").strip():
        raise ReglaNegocio(
            "'aprobado_con_condiciones' exige detallar las condiciones"
        )
    if ejecuta_area is not None and ejecuta_area not in parametros.MODULOS:
        raise ReglaNegocio(f"área ejecutora desconocida: {ejecuta_area}")

    return DecisionGerencialRepo(session).add(
        DecisionGerencial(
            empresa_id=empresa_id,
            tipo=tipo,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            decidido_por_id=decidido_por_id,
            sustento=sustento,
            resultado=resultado,
            condiciones=condiciones,
            ejecuta_area=ejecuta_area,
            fecha=fecha,
            archivo_id=archivo_id,
        )
    )


def listar_decisiones(
    session: Session,
    empresa_id: uuid.UUID | None = None,
    referencia_tipo: str | None = None,
    referencia_id: uuid.UUID | None = None,
    tipo: str | None = None,
) -> list[DecisionGerencial]:
    return DecisionGerencialRepo(session).list(
        empresa_id, referencia_tipo, referencia_id, tipo
    )


def obtener_decision(session: Session, decision_id: uuid.UUID) -> DecisionGerencial:
    decision = DecisionGerencialRepo(session).get(decision_id)
    if decision is None or decision.deleted_at is not None:
        raise NoEncontrado("decisión gerencial no encontrada")
    return decision
