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
from src.modules.accounting.domain import plantillas as plantillas_pcge
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import Asiento, AsientoLinea
from src.modules.accounting.infrastructure.repositories import (
    AsientoRepo,
    CuentaContableRepo,
    ReglaAsientoRepo,
)
from src.modules.users.infrastructure.models import Empresa
from src.shared import fechas, tributos


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
        # Un asiento se imputa en la cuenta de último nivel, nunca en el
        # rubro que la agrupa: cargar a «42 Cuentas por pagar comerciales»
        # deja el mayor sin decir a qué proveedor, y el rubro pasa a tener
        # movimiento propio además del de sus divisionarias.
        if cuenta_repo.tiene_hijas(cuenta.id):
            raise ReglaNegocio(
                f"la cuenta {cuenta.codigo} agrupa a otras: el asiento se "
                "imputa en una cuenta de último nivel"
            )
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

    hoy = fechas.hoy()
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


def anular_asiento_por_origen(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    referencia_origen: str,
    actor_id: uuid.UUID | None = None,
) -> Asiento | None:
    """Reversa el asiento automático de un hecho que se deshizo.

    `None` si nunca se generó (sin regla configurada, o ya anulado): igual
    que el resto de la generación automática, deshacer algo que no existe no
    es un error que deba romper el proceso de origen.
    """
    original = AsientoRepo(session).get_por_origen(
        empresa_id, evento, referencia_origen
    )
    if original is None or original.estado != "registrado":
        return None
    return anular_asiento(session, original.id, actor_id=actor_id)


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


def crear_asiento_automatico_multilinea(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    fecha: date,
    glosa: str,
    referencia_origen: str,
    lineas: list[tuple[uuid.UUID, str, Decimal]],
) -> Asiento | None:
    """Asiento automático de N líneas — el asiento real del Perú.

    `crear_asiento_automatico` alcanza para dos líneas y ningún asiento
    peruano tiene dos: una venta gravada son tres (cobrar, IGV, ingreso) y
    una compra son cinco, contando el asiento de destino.

    Un descuadre acá **no se omite en silencio**, se levanta: a diferencia de
    «no hay regla configurada» o «no hay periodo abierto», que son estados
    legítimos de la empresa, una plantilla que no cuadra es un error del
    código y esconderlo lo deja vivo.
    """
    repo = AsientoRepo(session)
    if repo.existe_por_origen(empresa_id, evento, referencia_origen):
        return None
    periodo = periodos.periodo_de_fecha(session, empresa_id, fecha)
    if periodo is None or not rules.puede_registrar(periodo.estado):
        return None

    total_debe = sum((m for _, t, m in lineas if t == "debe"), Decimal(0))
    total_haber = sum((m for _, t, m in lineas if t == "haber"), Decimal(0))
    if not rules.cuadra(total_debe, total_haber):
        raise ReglaNegocio(
            f"asiento automático descuadrado ({evento}): "
            f"debe {total_debe} != haber {total_haber}"
        )

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
    for cuenta_id, tipo, monto in lineas:
        session.add(
            AsientoLinea(
                asiento_id=asiento.id, cuenta_contable_id=cuenta_id, tipo=tipo, monto=monto
            )
        )
    session.flush()
    event_bus.publish(
        "accounting.asiento_generado",
        {"asiento_id": str(asiento.id), "evento_origen": evento},
        session=session,
    )
    return asiento


def crear_asiento_desde_plantilla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    fecha: date,
    glosa: str,
    referencia_origen: str,
    monto: Decimal,
    gravado_igv: bool | None = None,
) -> Asiento | None:
    """Asiento del PCGE para el evento, si hay plantilla y la empresa tiene
    las cuentas.

    `gravado_igv` es la casilla del comprobante: `None` deja decidir al
    default de la empresa (`shared.tributos`). Solo llega en los eventos de
    comprobante — el resto no lo conoce, y por eso su asiento no lleva IGV.

    `None` —no error— cuando el evento no tiene plantilla o cuando falta
    alguna de sus cuentas: una empresa que todavía no importó el PCGE no
    puede quedarse sin poder vender por eso. Quien llama lo audita en el log.
    """
    plantilla = plantillas_pcge.PLANTILLAS.get(evento)
    if plantilla is None or monto <= 0:
        return None
    empresa = session.get(Empresa, empresa_id)
    if empresa is None:
        return None
    importes = plantillas_pcge.desagregar(
        monto, tributos.tasa_igv(empresa, gravado_igv), plantilla.monto_es
    )
    codigos = [linea.codigo for linea in plantilla.lineas]
    cuentas = CuentaContableRepo(session).get_by_codigos(empresa_id, codigos)
    if any(codigo not in cuentas for codigo in codigos):
        return None

    # Una línea en cero no se escribe: con IGV exonerado, el asiento de venta
    # es de dos líneas y no de tres con una que dice 0.00.
    lineas = [
        (cuentas[linea.codigo].id, linea.tipo, importes[linea.importe])
        for linea in plantilla.lineas
        if importes[linea.importe] > 0
    ]
    if len(lineas) < 2:
        return None
    return crear_asiento_automatico_multilinea(
        session,
        empresa_id=empresa_id,
        evento=evento,
        fecha=fecha,
        glosa=glosa,
        referencia_origen=referencia_origen,
        lineas=lineas,
    )


def crear_asiento_automatico_si_hay_regla(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    evento: str,
    fecha: date,
    glosa: str,
    referencia_origen: str,
    monto: Decimal,
    gravado_igv: bool | None = None,
) -> Asiento | None:
    """Genera el asiento del evento. Dos fuentes, en este orden:

    1. la `regla_asiento` vigente de la empresa, si la configuró — la empresa
       manda sobre el default de fábrica;
    2. la **plantilla del PCGE** (`domain/plantillas.py`), que es el asiento
       oficial peruano completo, con su desagregación de IGV y su asiento de
       destino.

    `None` si no hay ninguna de las dos (se omite y se audita en el log del
    llamador) — mismo criterio no bloqueante de siempre.
    """
    regla = ReglaAsientoRepo(session).get_vigente(empresa_id, evento)
    if regla is None:
        return crear_asiento_desde_plantilla(
            session,
            empresa_id=empresa_id,
            evento=evento,
            fecha=fecha,
            glosa=glosa,
            referencia_origen=referencia_origen,
            monto=monto,
            gravado_igv=gravado_igv,
        )
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
