"""Casos de uso: asiento contable. Manual (permiso `accounting.asiento_manual`,
RN-CTB-001 cuadre) y automático (generado por `application/listeners.py` desde
un evento operativo mapeado en `regla_asiento`). Anular NUNCA borra/edita —
crea el asiento inverso en el periodo abierto vigente (RN-CTB-002)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.accounting.application import periodos
from src.modules.accounting.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import Asiento, AsientoLinea
from src.modules.accounting.infrastructure.repositories import (
    AsientoRepo,
    CuentaContableRepo,
    ReglaAsientoRepo,
)


def _construir_lineas(
    session: Session, empresa_id: uuid.UUID, lineas: list[dict]
) -> tuple[list[AsientoLinea], Decimal, Decimal]:
    cuenta_repo = CuentaContableRepo(session)
    filas: list[AsientoLinea] = []
    total_debe = Decimal(0)
    total_haber = Decimal(0)
    for li in lineas:
        cuenta = cuenta_repo.get(li["cuenta_contable_id"])
        if cuenta is None or cuenta.empresa_id != empresa_id:
            raise NoEncontrado(f"cuenta {li['cuenta_contable_id']} no encontrada")
        if not cuenta.activa:
            raise ReglaNegocio(f"cuenta {cuenta.codigo} está inactiva")
        tipo = li["tipo"]
        if tipo not in ("debe", "haber"):
            raise ReglaNegocio(f"tipo de línea inválido: {tipo}")
        monto = Decimal(str(li["monto"]))
        if monto <= 0:
            raise ReglaNegocio("el monto de una línea debe ser > 0")
        if tipo == "debe":
            total_debe += monto
        else:
            total_haber += monto
        filas.append(AsientoLinea(cuenta_contable_id=cuenta.id, tipo=tipo, monto=monto))
    return filas, total_debe, total_haber


def crear_asiento_manual(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    fecha: date,
    glosa: str,
    lineas: list[dict],  # [{cuenta_contable_id, tipo: "debe"|"haber", monto}]
    creado_por: uuid.UUID,
) -> Asiento:
    if len(lineas) < 2:
        raise ReglaNegocio("un asiento requiere al menos 2 líneas")
    filas, total_debe, total_haber = _construir_lineas(session, empresa_id, lineas)
    if not rules.cuadra(total_debe, total_haber):
        raise ReglaNegocio(f"asiento descuadrado: debe {total_debe} != haber {total_haber}")
    periodo = periodos.periodo_de_fecha(session, empresa_id, fecha)
    if periodo is None or not rules.puede_registrar(periodo.estado):
        raise Conflicto(f"no hay periodo contable abierto para {fecha.isoformat()}")

    asiento = AsientoRepo(session).add(
        Asiento(
            empresa_id=empresa_id,
            periodo_contable_id=periodo.id,
            fecha=fecha,
            glosa=glosa,
            origen="manual",
            estado="registrado",
            creado_por=creado_por,
        )
    )
    for fila in filas:
        fila.asiento_id = asiento.id
        session.add(fila)
    session.flush()
    event_bus.publish(
        "accounting.asiento_generado",
        {"asiento_id": str(asiento.id), "evento_origen": "manual"},
        session=session,
    )
    return asiento


def anular_asiento(session: Session, asiento_id: uuid.UUID, *, actor_id: uuid.UUID) -> Asiento:
    repo = AsientoRepo(session)
    original = repo.get(asiento_id)
    if original is None:
        raise NoEncontrado("asiento no encontrado")
    if original.estado != "registrado":
        raise Conflicto(f"el asiento ya está {original.estado}")

    hoy = date.today()
    periodo = periodos.periodo_de_fecha(session, original.empresa_id, hoy)
    if periodo is None or not rules.puede_registrar(periodo.estado):
        raise Conflicto("no hay periodo contable abierto para registrar la reversión")

    reversa = repo.add(
        Asiento(
            empresa_id=original.empresa_id,
            periodo_contable_id=periodo.id,
            fecha=hoy,
            glosa=f"Reversión de asiento {original.id}: {original.glosa}",
            origen="manual",
            estado="registrado",
            creado_por=actor_id,
            asiento_reversa_de_id=original.id,
        )
    )
    for linea in repo.lineas(original.id):
        session.add(
            AsientoLinea(
                asiento_id=reversa.id,
                cuenta_contable_id=linea.cuenta_contable_id,
                tipo="haber" if linea.tipo == "debe" else "debe",
                monto=linea.monto,
            )
        )
    original.estado = "anulado"
    session.flush()
    event_bus.publish(
        "accounting.asiento_generado",
        {"asiento_id": str(reversa.id), "evento_origen": "reversion"},
        session=session,
    )
    return reversa


def crear_asiento_automatico(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    fecha: date,
    glosa: str,
    referencia_origen: str,
    monto: Decimal,
    cuenta_debe_id: uuid.UUID,
    cuenta_haber_id: uuid.UUID,
) -> Asiento | None:
    """`None` si no hay periodo abierto o si ya existe un asiento para este
    evento+referencia — el listener nunca debe bloquear ni duplicar."""
    repo = AsientoRepo(session)
    if repo.existe_por_origen(empresa_id, evento, referencia_origen):
        return None
    periodo = periodos.periodo_de_fecha(session, empresa_id, fecha)
    if periodo is None or not rules.puede_registrar(periodo.estado):
        return None

    asiento = repo.add(
        Asiento(
            empresa_id=empresa_id,
            periodo_contable_id=periodo.id,
            fecha=fecha,
            glosa=glosa,
            origen="automatico",
            evento_origen=evento,
            referencia_origen=referencia_origen,
            estado="registrado",
        )
    )
    session.add(
        AsientoLinea(
            asiento_id=asiento.id, cuenta_contable_id=cuenta_debe_id, tipo="debe", monto=monto
        )
    )
    session.add(
        AsientoLinea(
            asiento_id=asiento.id, cuenta_contable_id=cuenta_haber_id, tipo="haber", monto=monto
        )
    )
    session.flush()
    event_bus.publish(
        "accounting.asiento_generado",
        {"asiento_id": str(asiento.id), "evento_origen": evento},
        session=session,
    )
    return asiento


def crear_asiento_automatico_si_hay_regla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    fecha: date,
    glosa: str,
    referencia_origen: str,
    monto: Decimal,
) -> Asiento | None:
    """Busca la `regla_asiento` vigente de la empresa para `evento` y genera
    el asiento si existe. `None` si no hay regla configurada (se omite, se
    audita en el log del llamador) — mismo criterio no bloqueante que el
    resto de la generación automática."""
    regla = ReglaAsientoRepo(session).get_vigente(empresa_id, evento)
    if regla is None:
        return None
    return crear_asiento_automatico(
        session,
        empresa_id=empresa_id,
        evento=evento,
        fecha=fecha,
        glosa=glosa,
        referencia_origen=referencia_origen,
        monto=monto,
        cuenta_debe_id=regla.cuenta_debe_id,
        cuenta_haber_id=regla.cuenta_haber_id,
    )
