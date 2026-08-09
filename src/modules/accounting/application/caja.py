"""Ciclo de caja (PROC-CTB-001/002): apertura, movimientos, cierre, arqueo,
custodia del efectivo y corrección de un cierre.

Tres cosas hacen que el ciclo cierre de verdad y no solo se registre:

1. **Nadie declara un monto sin contarlo** (RN-POS-003/007): tanto la
   apertura como el cierre reciben el conteo por billete y moneda, y el
   monto sale de esa suma. Lo que el encargado dice haber entregado se
   compara contra lo contado, y la diferencia se calcula — no se teclea.
2. **Cada relevo lo firma quien recibe** (RN-MDP-002): abrir y cerrar exigen
   la elevación de PIN del encargado (`POST /auth/autorizar`), y el
   efectivo sigue viajando por `custodia_efectivo` hasta quedar disponible.
3. **Un cierre con faltante se corrige, no se reescribe** (RN-MDP-005): la
   reapertura queda registrada con motivo y autorizador en
   `cierre_caja.correcciones`.

La apertura **nunca se bloquea** por falta de sencillo o por un POS
averiado (RN-POS-011): el local abre en su horario y el problema queda
reportado a contabilidad y gerencia por evento.

`accounting` no importa el dominio de `sales` (CLAUDE.md): el monto
esperado del cierre se reconcilia vía el contrato público
`sales.application.queries_publicas.total_efectivo_cobrado`, nunca
importando `Venta`/`Pago` directo.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.accounting.application.errors import Conflicto, NoEncontrado
from src.modules.accounting.domain import rules
from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    Arqueo,
    CierreCaja,
    CustodiaEfectivo,
    MovimientoCaja,
)
from src.modules.accounting.infrastructure.repositories import (
    AperturaCajaRepo,
    ArqueoRepo,
    CierreCajaRepo,
    CustodiaEfectivoRepo,
    MovimientoCajaRepo,
    PosTarjetaRepo,
)
from src.modules.sales.application.queries_publicas import (
    puntos_venta_de_empresa,
    puntos_venta_rotulados,
    sucursal_de_punto_venta,
    total_efectivo_cobrado,
    total_tarjeta_cobrado,
)
from src.shared import auditoria, fechas


def _contar(detalle: dict | None, que: str) -> Decimal:
    """Total del conteo por denominación, o `Conflicto` si no es un conteo.

    Un conteo vacío es válido y vale cero: la caja abre igual aunque no haya
    llegado el sencillo (RN-POS-011), y puede cerrarse con el cajón vacío si
    ya se retiró todo. Lo que no se acepta es *no contar*.
    """
    if detalle is None:
        raise Conflicto(f"{que} requiere el conteo por denominación (RN-POS-003)")
    desconocidas = rules.denominaciones_desconocidas(detalle)
    if desconocidas:
        raise Conflicto(f"denominaciones que no son de curso legal: {desconocidas}")
    try:
        return rules.total_denominaciones(detalle)
    except ValueError as e:
        raise Conflicto(str(e)) from e


def _relevo(rol: str, usuario_id: uuid.UUID) -> dict:
    return {
        "rol": rol,
        "usuario_id": str(usuario_id),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def abrir_caja(
    session: Session,
    *,
    punto_venta_id: uuid.UUID,
    cajero_id: uuid.UUID,
    relevo_encargado_id: uuid.UUID,
    monto_declarado: Decimal,
    detalle_denominaciones: dict,
    pos_verificados: list[dict] | None = None,
) -> AperturaCaja:
    """Abre el turno con el efectivo contado y los POS verificados.

    `relevo_encargado_id` sale de la elevación de PIN del encargado, no del
    cuerpo del request: un identificador suelto sería una firma
    falsificable y la cadena de custodia dejaría de probar nada.
    """
    repo = AperturaCajaRepo(session)
    if repo.abierta_en(punto_venta_id) is not None:
        raise Conflicto("ya hay una caja abierta en este punto de venta")
    if relevo_encargado_id == cajero_id:
        # Un relevo de uno solo no es un relevo (RN-MDP-002).
        raise Conflicto("el encargado que releva no puede ser el mismo cajero")

    monto_apertura = _contar(detalle_denominaciones, "la apertura de caja")
    # Lo contado contra lo que el encargado dice haber entregado. No bloquea
    # la apertura (RN-POS-011): queda reportado y el local abre igual.
    diferencia = monto_apertura - monto_declarado

    apertura = repo.add(
        AperturaCaja(
            punto_venta_id=punto_venta_id,
            cajero_id=cajero_id,
            relevo_encargado_id=relevo_encargado_id,
            monto_apertura=monto_apertura,
            detalle_denominaciones=detalle_denominaciones,
            diferencia_reportada=diferencia if diferencia != 0 else None,
            pos_verificados=_verificar_pos(session, pos_verificados),
        )
    )
    event_bus.publish(
        "accounting.apertura_caja_registrada",
        {
            "apertura_caja_id": str(apertura.id),
            "punto_venta_id": str(punto_venta_id),
            "diferencia_reportada": str(diferencia) if diferencia else None,
        },
        session=session,
    )
    return apertura


def _verificar_pos(session: Session, verificados: list[dict] | None) -> list | None:
    """Registra el estado de cada POS de tarjeta al abrir (RN-POS-010).

    Un terminal averiado **no impide abrir** (RN-POS-011): se marca en el
    inventario y se avisa, para que contabilidad mande el de emergencia
    (RN-POS-009) mientras la sucursal sigue vendiendo.
    """
    if not verificados:
        return None
    repo = PosTarjetaRepo(session)
    registro = []
    for v in verificados:
        pos = repo.get(uuid.UUID(str(v["pos_tarjeta_id"])))
        if pos is None:
            raise NoEncontrado(f"POS de tarjeta no encontrado: {v['pos_tarjeta_id']}")
        operativo = bool(v.get("operativo", True))
        if not operativo and pos.estado == "operativo":
            pos.estado = "averiado"
            event_bus.publish(
                "accounting.pos_averiado_reportado",
                {
                    "pos_tarjeta_id": str(pos.id),
                    "serie": pos.serie,
                    "sucursal_id": str(pos.sucursal_id) if pos.sucursal_id else None,
                    "observacion": v.get("observacion"),
                },
                session=session,
            )
        elif operativo and pos.estado == "averiado":
            pos.estado = "operativo"
        registro.append(
            {
                "pos_tarjeta_id": str(pos.id),
                "serie": pos.serie,
                "operativo": operativo,
                "observacion": v.get("observacion"),
            }
        )
    return registro


def registrar_movimiento_caja(
    session: Session,
    apertura_caja_id: uuid.UUID,
    *,
    tipo: str,
    monto: Decimal,
    motivo: str,
    registrado_por: uuid.UUID,
    idempotency_key: str,
    autorizado_por: uuid.UUID | None = None,
) -> MovimientoCaja:
    """Ingreso o retiro de efectivo del cajón durante el turno (RN-MDP-007).

    El turno real no es solo vender: se le paga al repartidor, se compra
    hielo, entra el vuelto que faltaba. Sin registrarlo, el cierre cuadra
    contra un esperado irreal y el descuadre se le atribuye al cajero.

    **Retirar exige autorización de supervisor**; ingresar no: meter plata
    al cajón no es la operación de la que hay que desconfiar.
    """
    repo = MovimientoCajaRepo(session)
    existente = repo.get_by_idempotency(idempotency_key)
    if existente is not None:
        return existente

    apertura = AperturaCajaRepo(session).get(apertura_caja_id)
    if apertura is None:
        raise NoEncontrado("apertura de caja no encontrada")
    if CierreCajaRepo(session).get_by_apertura(apertura_caja_id) is not None:
        raise Conflicto("la caja ya está cerrada; no admite movimientos")
    if tipo not in ("ingreso", "retiro"):
        raise Conflicto(f"tipo de movimiento inválido: {tipo}")
    if monto <= 0:
        raise Conflicto("el monto debe ser > 0")
    if not (motivo or "").strip():
        raise Conflicto("el movimiento de efectivo requiere motivo")
    if tipo == "retiro" and autorizado_por is None:
        raise Conflicto("retirar efectivo requiere autorización de supervisor")

    if tipo == "retiro":
        # No se puede sacar más de lo que hay: el cajón no da crédito.
        disponible = (
            apertura.monto_apertura
            + total_efectivo_cobrado(
                session, apertura.punto_venta_id, apertura.created_at
            )
            + repo.neto(apertura_caja_id)
        )
        if monto > disponible:
            raise Conflicto(
                f"el retiro excede el efectivo en caja ({disponible})"
            )

    movimiento = repo.add(
        MovimientoCaja(
            apertura_caja_id=apertura_caja_id,
            tipo=tipo,
            monto=monto,
            motivo=motivo.strip(),
            registrado_por=registrado_por,
            autorizado_por=autorizado_por,
            idempotency_key=idempotency_key,
        )
    )
    # Plata que entra o sale del cajón fuera de la venta: al rastro con
    # quién lo registró y quién lo autorizó (RN-MDP-007).
    auditoria.registrar(
        session,
        usuario_id=registrado_por,
        entidad="movimiento_caja",
        entidad_id=movimiento.id,
        accion=f"{tipo}_efectivo",
        datos_despues={
            "monto": str(monto),
            "motivo": movimiento.motivo,
            "autorizado_por": str(autorizado_por) if autorizado_por else None,
            "apertura_caja_id": str(apertura_caja_id),
        },
    )
    event_bus.publish(
        "accounting.movimiento_caja_registrado",
        {
            "movimiento_caja_id": str(movimiento.id),
            "apertura_caja_id": str(apertura_caja_id),
            "tipo": tipo,
            "monto": str(monto),
            "motivo": movimiento.motivo,
        },
    )
    return movimiento


def efectivo_esperado(session: Session, apertura: AperturaCaja) -> dict:
    """Desglose de lo que debería haber en el cajón, ahora.

    Apertura + cobros en efectivo del turno + ingresos − retiros. Los tres
    sumandos van por separado porque un descuadre se investiga distinto
    según de cuál venga.
    """
    cobrado = total_efectivo_cobrado(
        session, apertura.punto_venta_id, apertura.created_at
    )
    movimientos = MovimientoCajaRepo(session).neto(apertura.id)
    return {
        "apertura": apertura.monto_apertura,
        "cobrado": cobrado,
        "movimientos": movimientos,
        "esperado": apertura.monto_apertura + cobrado + movimientos,
    }


def _cuadre_de_tarjetas(
    session: Session, apertura: AperturaCaja, reportes_pos: list | None
) -> dict:
    """Lo cobrado con tarjeta contra lo que declaran los lotes (RN-POS-004).

    Exige el reporte de **cada terminal que la apertura dio por operativo**:
    uno averiado no cobró nada, así que no se le pide. Un local sin
    terminales verificados no tiene nada que cuadrar y esto no estorba.
    """
    faltantes = rules.pos_sin_reporte(apertura.pos_verificados, reportes_pos)
    if faltantes:
        raise Conflicto(
            "falta el reporte de lote de estos POS operativos: " + ", ".join(faltantes)
        )
    cobrado = total_tarjeta_cobrado(
        session, apertura.punto_venta_id, apertura.created_at
    )
    declarado = rules.total_declarado_en_pos(reportes_pos)
    return {
        "cobrado": cobrado,
        "declarado": declarado,
        "descuadre": declarado - cobrado,
    }


def cerrar_caja(
    session: Session,
    apertura_caja_id: uuid.UUID,
    *,
    cajero_id: uuid.UUID,
    receptor_id: uuid.UUID,
    detalle_denominaciones: dict,
    custodia: str,
    descuadre_atribucion: str | None = None,
    reportes_pos: list | None = None,
) -> CierreCaja:
    """Cierra el turno: cuenta el cajón, cuadra las tarjetas y entrega el
    efectivo.

    El cierre no cuadra solo efectivo (RN-POS-004): cada POS que abrió
    operativo trae su reporte de lote, y la suma se contrasta con lo cobrado
    con tarjeta en el turno. `descuadre_monto` sigue siendo **el del cajón**
    —es la plata que alguien tiene que responder— y el de tarjetas viaja en
    `montos_esperados`/`montos_reales`; cualquiera de los dos marca el
    cierre como irregular.

    Si el cierre venía reabierto (`en_proceso`), este mismo caso de uso lo
    **recalcula sobre el registro existente**: la corrección de un cierre no
    crea un segundo cierre del mismo turno, deja rastro en el primero.
    """
    apertura = AperturaCajaRepo(session).get(apertura_caja_id)
    if apertura is None:
        raise NoEncontrado("apertura de caja no encontrada")
    if receptor_id == cajero_id:
        raise Conflicto("el encargado que recibe no puede ser el mismo cajero")

    cierre = CierreCajaRepo(session).get_by_apertura(apertura_caja_id)
    if cierre is not None and cierre.estado != "en_proceso":
        raise Conflicto("esta apertura ya tiene un cierre registrado")

    monto_real = _contar(detalle_denominaciones, "el cierre de caja")
    desglose = efectivo_esperado(session, apertura)
    descuadre = monto_real - desglose["esperado"]
    tarjetas = _cuadre_de_tarjetas(session, apertura, reportes_pos)
    # Un descuadre en cualquiera de los dos frentes deja el cierre irregular:
    # cuadrar el cajón no dice nada de lo que pasó por los terminales.
    estado = (
        "conforme" if descuadre == 0 and tarjetas["descuadre"] == 0 else "con_irregularidad"
    )
    montos_esperados = {k: str(v) for k, v in desglose.items()}
    montos_esperados["tarjeta"] = str(tarjetas["cobrado"])
    montos_reales = {
        "efectivo": str(monto_real),
        "denominaciones": detalle_denominaciones,
        "tarjeta": str(tarjetas["declarado"]),
        "descuadre_tarjeta": str(tarjetas["descuadre"]),
    }

    if cierre is None:
        cierre = CierreCajaRepo(session).add(
            CierreCaja(
                apertura_caja_id=apertura_caja_id,
                cajero_id=cajero_id,
                montos_esperados=montos_esperados,
                montos_reales=montos_reales,
                descuadre_monto=descuadre,
                descuadre_atribucion=descuadre_atribucion if estado != "conforme" else None,
                reportes_pos=reportes_pos,
                custodia=custodia,
                estado=estado,
                relevos=[_relevo("cajero", cajero_id), _relevo("encargado", receptor_id)],
            )
        )
    else:
        cierre.montos_esperados = montos_esperados
        cierre.montos_reales = montos_reales
        cierre.descuadre_monto = descuadre
        cierre.descuadre_atribucion = descuadre_atribucion if estado != "conforme" else None
        cierre.reportes_pos = reportes_pos
        cierre.custodia = custodia
        cierre.estado = estado
        cierre.relevos = (cierre.relevos or []) + [_relevo("encargado", receptor_id)]

    _abrir_custodia(session, apertura_caja_id, monto_real, receptor_id)
    event_bus.publish(
        "accounting.cierre_caja_registrado",
        {
            "cierre_caja_id": str(cierre.id),
            "apertura_caja_id": str(apertura_caja_id),
            "descuadre_monto": str(descuadre),
        },
        session=session,
    )
    if estado == "con_irregularidad":
        event_bus.publish(
            "accounting.cierre_caja_irregular",
            # `sucursal_id` desde 2026-08-08: la caja cuelga del punto de
            # venta, no de la sucursal, y `reports` necesita el local para
            # escopar el reporte y elegir la regla de distribución.
            {
                "cierre_caja_id": str(cierre.id),
                "sucursal_id": str(
                    sucursal_de_punto_venta(session, apertura.punto_venta_id)
                ),
                "descuadre_monto": str(descuadre),
                "descuadre_tarjeta": str(tarjetas["descuadre"]),
                "descuadre_atribucion": descuadre_atribucion,
            },
            session=session,
        )
    return cierre


def _abrir_custodia(
    session: Session,
    apertura_caja_id: uuid.UUID,
    monto: Decimal,
    receptor_id: uuid.UUID,
) -> CustodiaEfectivo:
    """El efectivo pasa del cajero al encargado al cerrar (RN-MDP-002).

    Nace en `en_supervisor` y no en `en_caja` porque el cierre ya exigió la
    firma del encargado: el tramo cajero→encargado acaba de ocurrir.
    """
    repo = CustodiaEfectivoRepo(session)
    custodia = repo.de_apertura(apertura_caja_id)
    if custodia is not None:
        # Cierre recalculado tras una reapertura: el monto cambió, el
        # responsable sigue siendo el mismo tramo de la cadena.
        custodia.monto = monto
        return custodia
    return repo.add(
        CustodiaEfectivo(
            apertura_caja_id=apertura_caja_id,
            monto=monto,
            responsable_actual_id=receptor_id,
            estado="en_supervisor",
            timestamps_relevo=[_relevo("encargado", receptor_id)],
        )
    )


def entregar_custodia(
    session: Session,
    custodia_id: uuid.UUID,
    *,
    estado_siguiente: str,
    receptor_id: uuid.UUID,
) -> CustodiaEfectivo:
    """Avanza la cadena de custodia; quien recibe firma con su PIN."""
    custodia = CustodiaEfectivoRepo(session).get(custodia_id)
    if custodia is None:
        raise NoEncontrado("custodia de efectivo no encontrada")
    if not rules.puede_entregar_custodia(custodia.estado, estado_siguiente):
        raise Conflicto(
            f"la custodia no puede pasar de {custodia.estado} a {estado_siguiente}"
        )
    custodia.estado = estado_siguiente
    custodia.responsable_actual_id = receptor_id
    custodia.timestamps_relevo = (custodia.timestamps_relevo or []) + [
        _relevo(estado_siguiente, receptor_id)
    ]
    event_bus.publish(
        "accounting.custodia_efectivo_entregada",
        {
            "custodia_efectivo_id": str(custodia.id),
            "apertura_caja_id": str(custodia.apertura_caja_id),
            "estado": estado_siguiente,
            "monto": str(custodia.monto),
        },
        session=session,
    )
    return custodia


def reabrir_cierre(
    session: Session,
    cierre_id: uuid.UUID,
    *,
    motivo: str,
    autorizado_por: uuid.UUID,
) -> CierreCaja:
    """Devuelve un cierre a `en_proceso` para recontar (RN-MDP-005).

    No borra nada: el descuadre anterior queda en `correcciones` junto con
    quién autorizó y por qué. Sin esto, un cierre con faltante solo se podía
    mirar — y en la práctica se "arreglaba" tecleando otro número en la BD.
    """
    cierre = CierreCajaRepo(session).get(cierre_id)
    if cierre is None:
        raise NoEncontrado("cierre de caja no encontrado")
    if not (motivo or "").strip():
        raise Conflicto("la reapertura requiere motivo")
    custodia = CustodiaEfectivoRepo(session).de_apertura(cierre.apertura_caja_id)
    estado_custodia = custodia.estado if custodia else "en_caja"
    if not rules.puede_reabrir_cierre(cierre.estado, estado_custodia):
        raise Conflicto(
            f"no se puede reabrir un cierre {cierre.estado} con el efectivo "
            f"{estado_custodia}"
        )

    cierre.correcciones = (cierre.correcciones or []) + [
        {
            "motivo": motivo.strip(),
            "autorizado_por": str(autorizado_por),
            "descuadre_anterior": str(cierre.descuadre_monto),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    ]
    cierre.estado = "en_proceso"
    event_bus.publish(
        "accounting.cierre_caja_reabierto",
        {
            "cierre_caja_id": str(cierre.id),
            "apertura_caja_id": str(cierre.apertura_caja_id),
            "motivo": motivo.strip(),
            "autorizado_por": str(autorizado_por),
        },
        session=session,
    )
    return cierre


def registrar_arqueo(
    session: Session,
    *,
    punto_venta_id: uuid.UUID,
    tipo: str,
    realizado_por: uuid.UUID,
    monto_contado: Decimal,
) -> Arqueo:
    apertura = AperturaCajaRepo(session).abierta_en(punto_venta_id)
    if apertura is None:
        raise NoEncontrado("no hay caja abierta en este punto de venta")

    monto_esperado = efectivo_esperado(session, apertura)["esperado"]
    diferencia = monto_contado - monto_esperado

    arqueo = ArqueoRepo(session).add(
        Arqueo(
            punto_venta_id=punto_venta_id,
            tipo=tipo,
            realizado_por=realizado_por,
            monto_esperado=monto_esperado,
            monto_contado=monto_contado,
            diferencia=diferencia,
        )
    )
    event_bus.publish(
        "accounting.arqueo_registrado",
        {
            "arqueo_id": str(arqueo.id),
            "punto_venta_id": str(punto_venta_id),
            "diferencia_monto": str(diferencia),
        },
        session=session,
    )
    return arqueo


def turnos_cerrados(
    session: Session,
    empresa_id: uuid.UUID | None,
    *,
    desde: date,
    hasta: date,
) -> list[dict]:
    """Turnos cerrados de la empresa en el rango, con custodia y descuadre.

    Es la lista sobre la que trabaja contabilidad: reabrir un cierre con
    faltante (RN-MDP-005) y recibir el efectivo (RN-MDP-002) se hacen sobre
    un turno concreto, y sin este listado hacía falta conocer de memoria el
    id de la apertura para llegar a cualquiera de las dos cosas.
    """
    punto_venta_ids = puntos_venta_de_empresa(session, empresa_id)
    filas = CierreCajaRepo(session).cerrados_entre(
        punto_venta_ids, fechas.inicio_dia_utc(desde), fechas.fin_dia_utc(hasta)
    )
    # El rótulo lo da `sales`, dueño de `punto_venta` (mismo contrato público
    # que usa el reporte de estado de caja): una tabla de turnos que no dice
    # de qué caja habla no sirve para ir a reclamar un faltante.
    rotulos = puntos_venta_rotulados(session, [a.punto_venta_id for _, a, _ in filas])
    return [
        {
            "cierre_id": cierre.id,
            "apertura_caja_id": apertura.id,
            "punto_venta_id": apertura.punto_venta_id,
            "caja": rotulos.get(apertura.punto_venta_id, "(sin rótulo)"),
            "cajero_id": apertura.cajero_id,
            "abierta_desde": apertura.created_at,
            "monto_apertura": apertura.monto_apertura,
            "descuadre_monto": cierre.descuadre_monto,
            "descuadre_atribucion": cierre.descuadre_atribucion,
            "estado": cierre.estado,
            "custodia_destino": cierre.custodia,
            "custodia_id": custodia.id if custodia else None,
            "custodia_estado": custodia.estado if custodia else None,
            "custodia_monto": custodia.monto if custodia else None,
            "correcciones": cierre.correcciones,
        }
        for cierre, apertura, custodia in filas
    ]


def cajas_abiertas(session: Session, empresa_id: uuid.UUID | None = None) -> list[dict]:
    """Estado actual de caja por punto de venta de la empresa — para el
    dashboard gerencial (`core.dashboard_router`)."""
    punto_venta_ids = puntos_venta_de_empresa(session, empresa_id)
    aperturas = AperturaCajaRepo(session).abiertas_de(punto_venta_ids)
    return [
        {
            "apertura_caja_id": a.id,
            "punto_venta_id": a.punto_venta_id,
            "cajero_id": a.cajero_id,
            "monto_apertura": a.monto_apertura,
            "abierta_desde": a.created_at,
            "pos_verificados": a.pos_verificados,
        }
        for a in aperturas
    ]
