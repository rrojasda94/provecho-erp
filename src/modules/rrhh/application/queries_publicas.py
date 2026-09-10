"""Contrato público de lectura de `rrhh` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para leer datos de `rrhh` desde afuera, devolviendo DTOs (dicts),
nunca el ORM. Nadie importa `rrhh.infrastructure` desde otro módulo.

Lo que se expone acá es deliberadamente lo **mínimo identificatorio**:
nombre y cargo para poder etiquetar un ranking. Remuneración, régimen
pensionario, contratos y sanciones no salen de `rrhh` por ningún contrato
— quien los necesite pasa por su API con `rrhh.leer`.
"""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.rrhh.infrastructure.models import Asistencia, Trabajador
from src.modules.users.infrastructure.models import Persona, Usuario


def nombres_por_usuario(
    session: Session, usuario_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict]:
    """`usuario_id` → nombre y cargo del trabajador, para etiquetar reportes
    de otros módulos (ej. ranking de venta por quien atendió).

    Un `usuario_id` sin trabajador asociado no aparece en el resultado: hay
    usuarios que no son personal (la cuenta de servicio del hub, el
    `agente_ia`). Quien llama decide cómo mostrarlos — inventar un nombre
    acá sería peor.

    La cuenta se resuelve por persona (ADR-070), y una persona recontratada
    puede tener dos filas `trabajador` compartiendo la misma cuenta. Entre
    esas, gana la que no está cesada, y si hay empate la de ingreso más
    reciente — sin este orden, el ranking podía etiquetar a alguien con su
    cargo viejo.
    """
    if not usuario_ids:
        return {}
    filas = session.execute(
        select(Usuario.id, Persona.nombres, Persona.apellidos, Trabajador.cargo)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .join(Usuario, Usuario.persona_id == Trabajador.persona_id)
        .where(
            Usuario.id.in_(list(usuario_ids)),
            Usuario.deleted_at.is_(None),
            Trabajador.deleted_at.is_(None),
        )
        .order_by(
            (Trabajador.estado == "cesado").asc(),
            Trabajador.fecha_ingreso.desc(),
        )
    )
    resultado: dict[uuid.UUID, dict] = {}
    for usuario_id, nombres, apellidos, cargo in filas:
        # Primero gana: ya vienen ordenadas activo-primero / más reciente.
        resultado.setdefault(
            usuario_id, {"nombre": f"{nombres} {apellidos}".strip(), "cargo": cargo}
        )
    return resultado


def horas_asistidas(
    session: Session, trabajador_ids: Sequence[uuid.UUID], fecha: date
) -> dict[uuid.UUID, Decimal]:
    """`trabajador_id` → horas trabajadas esa `fecha`, para que quien
    necesite un dato de horas-hombre real (ej. `production` al costear
    RN-PRD-018) no dependa de que alguien lo tipee.

    Horas = (`hora_salida` − `hora_entrada`) + `horas_extra` (RN-RRHH-022:
    la carga siempre RRHH a mano, nunca el pad). Sin `hora_entrada` o sin
    `hora_salida` marcada todavía —el turno sigue abierto, o nadie marcó—
    el día no cuenta: 0 horas, no una hora parcial que nadie puede
    reconstruir después. Un `trabajador_id` sin fila de asistencia esa
    fecha tampoco aparece en el resultado — quien llama decide qué hacer
    con "no marcó" (RN-RRHH-009).
    """
    if not trabajador_ids:
        return {}
    filas = session.execute(
        select(
            Asistencia.trabajador_id,
            Asistencia.hora_entrada,
            Asistencia.hora_salida,
            Asistencia.horas_extra,
        ).where(
            Asistencia.trabajador_id.in_(list(trabajador_ids)),
            Asistencia.fecha == fecha,
        )
    )
    resultado: dict[uuid.UUID, Decimal] = {}
    for trabajador_id, hora_entrada, hora_salida, horas_extra in filas:
        if hora_entrada is None or hora_salida is None:
            resultado[trabajador_id] = Decimal("0.00")
            continue
        # `time` no se resta directo (Python no lo permite): se ancla a la
        # misma fecha arbitraria para poder restar los `datetime` resultantes.
        segundos = (
            datetime.combine(date.min, hora_salida)
            - datetime.combine(date.min, hora_entrada)
        ).total_seconds()
        trabajadas = Decimal(segundos) / Decimal(3600)
        resultado[trabajador_id] = (trabajadas + horas_extra).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return resultado


def trabajadores_activos(
    session: Session, empresa_id: uuid.UUID, area: str | None = None
) -> list[dict]:
    """Trabajadores activos de la empresa, para elegir a quién imputar
    horas-hombre (ej. la orden de producción) sin exponer el resto de la
    ficha. `area` filtra por área operativa (ej. "Cocina") cuando quien
    llama ya sabe cuál busca — sin él, trae toda la empresa.
    """
    condiciones = [
        Trabajador.empresa_id == empresa_id,
        Trabajador.estado == "activo",
        Trabajador.deleted_at.is_(None),
    ]
    if area is not None:
        condiciones.append(Trabajador.area == area)
    filas = session.execute(
        select(Trabajador.id, Persona.nombres, Persona.apellidos, Trabajador.cargo)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .where(*condiciones)
        .order_by(Persona.nombres, Persona.apellidos)
    )
    return [
        {
            "id": trabajador_id,
            "nombre": f"{nombres} {apellidos}".strip(),
            "cargo": cargo,
        }
        for trabajador_id, nombres, apellidos, cargo in filas
    ]


def trabajador_resumen(session: Session, trabajador_id: uuid.UUID) -> dict | None:
    """Lo mínimo para que otro módulo valide a un trabajador como sujeto de
    algo suyo — hoy lo usa `assets` para el responsable de un activo y el
    sujeto de un documento con vencimiento (carné de sanidad, licencia de
    conducir). `None` si no existe o está borrado: quien llama decide si eso
    es un 404 o un dato opcional ausente.
    """
    fila = session.execute(
        select(Trabajador.id, Trabajador.empresa_id, Trabajador.sucursal_id,
               Trabajador.estado, Persona.nombres, Persona.apellidos)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .where(Trabajador.id == trabajador_id, Trabajador.deleted_at.is_(None))
    ).first()
    if fila is None:
        return None
    trabajador_id, empresa_id, sucursal_id, estado, nombres, apellidos = fila
    return {
        "id": trabajador_id,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
        "nombre": f"{nombres} {apellidos}".strip(),
        "estado": estado,
    }


def trabajadores_con_cuenta(session: Session, empresa_id: uuid.UUID) -> list[dict]:
    """Trabajadores activos de la empresa que tienen cuenta propia (ADR-070)
    — candidatos a repartidor propio (`delivery.gestionar_repartidores`,
    ADR-098): sin cuenta, no hay con qué entrar a la PWA a ver las rutas
    propias. Uno con vínculo de `locacion_servicios` sigue siendo elegible
    a propósito — repartir no es planilla, y RN-PER-002 no lo prohíbe.
    """
    filas = session.execute(
        select(
            Trabajador.id,
            Usuario.id,
            Persona.nombres,
            Persona.apellidos,
            Trabajador.cargo,
            Trabajador.sucursal_id,
        )
        .join(Persona, Persona.id == Trabajador.persona_id)
        .join(Usuario, Usuario.persona_id == Trabajador.persona_id)
        .where(
            Trabajador.empresa_id == empresa_id,
            Trabajador.estado == "activo",
            Trabajador.deleted_at.is_(None),
            Usuario.deleted_at.is_(None),
        )
        .order_by(Persona.nombres, Persona.apellidos)
    )
    return [
        {
            "trabajador_id": trabajador_id,
            "usuario_id": usuario_id,
            "nombre": f"{nombres} {apellidos}".strip(),
            "cargo": cargo,
            "sucursal_id": sucursal_id,
        }
        for trabajador_id, usuario_id, nombres, apellidos, cargo, sucursal_id in filas
    ]


def cuenta_de_trabajador(session: Session, trabajador_id: uuid.UUID) -> dict | None:
    """`usuario_id`, nombre, teléfono y alcance de un trabajador, para
    resolver el alta de un repartidor (`delivery.repartidores.crear`).

    `None` si el trabajador no existe, está cesado/borrado, o no tiene
    cuenta — los tres casos son "no se puede dar de alta", y quien llama no
    necesita distinguirlos para responder 409.
    """
    fila = session.execute(
        select(
            Usuario.id,
            Persona.nombres,
            Persona.apellidos,
            Persona.telefono,
            Trabajador.empresa_id,
            Trabajador.sucursal_id,
        )
        .select_from(Trabajador)
        .join(Persona, Persona.id == Trabajador.persona_id)
        .join(Usuario, Usuario.persona_id == Trabajador.persona_id)
        .where(
            Trabajador.id == trabajador_id,
            Trabajador.deleted_at.is_(None),
            Usuario.deleted_at.is_(None),
        )
    ).first()
    if fila is None:
        return None
    usuario_id, nombres, apellidos, telefono, empresa_id, sucursal_id = fila
    return {
        "usuario_id": usuario_id,
        "nombre": f"{nombres} {apellidos}".strip(),
        "telefono": telefono,
        "empresa_id": empresa_id,
        "sucursal_id": sucursal_id,
    }
