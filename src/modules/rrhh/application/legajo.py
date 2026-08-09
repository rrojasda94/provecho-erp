"""File personal del trabajador: todo su expediente en una sola lectura.

`docs/diagrams/Procesos/Recursos-Humanos/Contratacion/apertura-file-personal.md`
lo trata como **un** documento, y así lo pide quien lo consulta: nadie
pregunta "¿qué amonestaciones tiene?" sin querer ver también sus contratos y
sus permisos. Ocho endpoints separados serían ocho viajes para armar una
sola pantalla, y cada uno con su propio chequeo de permiso sobre el mismo
trabajador.

**Qué NO entra, y por qué:**

- **Asistencia**: es la única tabla que crece sin techo (una fila por día y
  por trabajador). Va por `GET /rrhh/asistencia` siempre acotada por rango.
- **Actas**: `acta` no cuelga de un trabajador —es un acto de la empresa—
  así que no hay legajo al que pertenezca.
- **Nómina** (boletas y liquidaciones), salvo permiso: ver abajo.

**La nómina se separa a propósito.** Boletas y liquidaciones llevan
remuneración, y `rrhh.leer` lo tiene el rol `supervisor`, que necesita ver
las amonestaciones y los permisos de su gente pero no cuánto gana. Que un
dato ya fuera legible pidiéndolo por su id no es razón para volverlo
navegable: la diferencia entre "se puede consultar" y "está a la vista" es
justamente el control. Quien tenga `rrhh.nomina_gestionar` lo ve; el resto
recibe el legajo sin esa parte y con `nomina_visible=False`, que es
información honesta y no un hueco silencioso.
"""

import uuid

from sqlalchemy.orm import Session

from src.modules.rrhh.application.errors import NoEncontrado
from src.modules.rrhh.infrastructure.models import Trabajador
from src.modules.rrhh.infrastructure.repositories import (
    AmonestacionRepo,
    AsistenciaRepo,
    BoletaPagoRepo,
    CertificadoTrabajoRepo,
    ContratoLaboralRepo,
    LiquidacionBssRepo,
    MemorandumRepo,
    PactoPermanenciaRepo,
    SolicitudPermisoRepo,
    TrabajadorRepo,
)


def legajo(
    session: Session,
    trabajador_id: uuid.UUID,
    *,
    incluir_nomina: bool = False,
) -> dict:
    """El expediente completo del trabajador.

    `incluir_nomina` lo decide el router según el permiso de quien pregunta,
    no el llamador según su criterio: acá solo se respeta la decisión.
    """
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise NoEncontrado("trabajador no encontrado")

    return {
        "trabajador": trabajador,
        "contratos": ContratoLaboralRepo(session).list_por_trabajador(trabajador_id),
        "amonestaciones": AmonestacionRepo(session).list_por_trabajador(trabajador_id),
        "memorandums": MemorandumRepo(session).list_por_trabajador(trabajador_id),
        "certificados": CertificadoTrabajoRepo(session).list_por_trabajador(
            trabajador_id
        ),
        "permisos": SolicitudPermisoRepo(session).list_por_trabajador(trabajador_id),
        "pactos_permanencia": PactoPermanenciaRepo(session).list_por_trabajador(
            trabajador_id
        ),
        "nomina_visible": incluir_nomina,
        "boletas": (
            BoletaPagoRepo(session).list_por_trabajador(trabajador_id)
            if incluir_nomina
            else []
        ),
        "liquidaciones": (
            LiquidacionBssRepo(session).list_por_trabajador(trabajador_id)
            if incluir_nomina
            else []
        ),
    }


def q_permisos(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    estado: str | None = None,
    trabajador_id: uuid.UUID | None = None,
):
    """Bandeja de solicitudes de permiso, sin ejecutar (ADR-026).

    Vive fuera del legajo porque quien aprueba **no entra por un
    trabajador**: entra por "qué tengo pendiente", que es una lista que
    cruza a toda la gente.
    """
    return SolicitudPermisoRepo(session).q_list(empresa_id, estado, trabajador_id)


def q_asistencia(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    trabajador_id: uuid.UUID | None = None,
    desde=None,
    hasta=None,
):
    """Marcaciones del rango, sin ejecutar (ADR-026)."""
    return AsistenciaRepo(session).q_list(empresa_id, trabajador_id, desde, hasta)


def empresa_de(session: Session, trabajador_id: uuid.UUID) -> uuid.UUID | None:
    """`empresa_id` del trabajador, para que el router valide el alcance sin
    cargar dos veces la misma fila."""
    trabajador = session.get(Trabajador, trabajador_id)
    return trabajador.empresa_id if trabajador else None
