"""Contrato público de lectura de `accounting` para otros módulos.

Mismo criterio que `sales.application.queries_publicas`: único punto de
entrada para leer datos de `accounting` desde afuera, devolviendo DTOs
(dicts), nunca el ORM.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.accounting.domain import plantillas
from src.modules.accounting.infrastructure.models import CuentaContable
from src.modules.accounting.infrastructure.repositories import (
    AperturaCajaRepo,
    CuentaContableRepo,
    MovimientoCajaRepo,
)
from src.modules.sales.application.queries_publicas import (
    puntos_venta_de_empresa,
    puntos_venta_de_sucursal,
    puntos_venta_rotulados,
    total_efectivo_cobrado,
)


def hay_caja_abierta(session: Session, punto_venta_id: uuid.UUID) -> bool:
    """¿Hay turno de caja abierto en ese punto de venta?

    Lo consulta `sales` antes de aceptar un cobro: cobrar sin caja abierta
    deja plata que no pertenece a ningún turno, así que el cierre no la
    espera y el descuadre aparece recién en contabilidad, sin responsable
    (RN-MDP-005). Es una lectura, no una importación de dominio: `sales`
    nunca ve `AperturaCaja`.
    """
    return AperturaCajaRepo(session).abierta_en(punto_venta_id) is not None


def encargado_de_turno(session: Session, sucursal_id: uuid.UUID) -> uuid.UUID | None:
    """Quién es el encargado **de turno** en esta sucursal, ahora.

    Se deriva del `relevo_encargado_id` de la caja abierta: el encargado que
    firmó la apertura era exactamente la persona a cargo del local en ese
    momento, y el dato ya se registraba al abrir turno.

    **Desde RN-MDP-008 el cajero abre solo**, así que las aperturas nuevas
    dejan esa columna en NULL y esta función devuelve `None` casi siempre.
    No se sustituye por el cajero: el cajero no es el encargado, y avisarle
    a él de un pedido demorado sería mandar el aviso a quien no puede
    resolverlo. Quien llama ya tiene respaldo por rol
    (`reports.destinatarios`, ADR-036) y ese respaldo pasa a ser el camino
    normal. Recuperar un encargado de turno de verdad necesita una fuente
    propia —un turno de personal, no la caja— y está anotado como deuda en
    `docs/roadmap/deuda/dashboard-y-caja.md`.

    `None` también si no hay caja abierta (local cerrado). Inventar un
    destinatario acá sería peor que decir que no se sabe.
    """
    puntos = puntos_venta_de_sucursal(session, sucursal_id)
    aperturas = AperturaCajaRepo(session).abiertas_de(puntos)
    if not aperturas:
        return None
    # Si hubiera varias cajas abiertas, la más reciente es la del turno en
    # curso.
    ultima = max(aperturas, key=lambda a: a.created_at)
    return ultima.relevo_encargado_id


def estado_de_caja(
    session: Session,
    empresa_id: uuid.UUID | None = None,
    *,
    ahora: datetime | None = None,
) -> list[dict]:
    """Caja abierta por punto de venta, **con cuánto lleva abierta y cuánto
    efectivo debería tener** — el KPI del dashboard solo cuenta cuántas hay.

    Es reporte y no solo indicador porque las tres cosas que preocupan de
    una caja abierta son distintas entre sí: llevar 14 horas abierta (nadie
    cerró el turno), acumular mucho efectivo (toca hacer retiro), y la
    diferencia declarada al abrir. Un número suelto no las distingue.

    Se ordena por horas abiertas descendente: lo primero que hay que mirar
    es la caja que nadie cerró.

    El efectivo esperado es apertura + cobros en efectivo desde la apertura
    + ingresos − retiros del turno (`movimiento_caja`, RN-MDP-007): el mismo
    número contra el que va a cuadrar el cierre.
    """
    ahora = ahora or datetime.now(tz=UTC)
    punto_venta_ids = puntos_venta_de_empresa(session, empresa_id)
    aperturas = AperturaCajaRepo(session).abiertas_de(punto_venta_ids)
    # El rótulo lo da `sales`, dueño de `punto_venta`: una tabla de cajas
    # que no dice de qué caja habla no sirve para ir a cerrarla.
    rotulos = puntos_venta_rotulados(session, [a.punto_venta_id for a in aperturas])

    filas = []
    for a in aperturas:
        desde = a.created_at
        if desde.tzinfo is None:
            # SQLite devuelve el timestamp sin zona; la base escribe en UTC.
            desde = desde.replace(tzinfo=UTC)
        horas = Decimal((ahora - desde).total_seconds()) / Decimal(3600)
        cobrado = total_efectivo_cobrado(session, a.punto_venta_id, desde)
        movimientos = MovimientoCajaRepo(session).neto(a.id)
        filas.append(
            {
                "apertura_caja_id": a.id,
                "punto_venta_id": a.punto_venta_id,
                "caja": rotulos.get(a.punto_venta_id, "(sin rótulo)"),
                "cajero_id": a.cajero_id,
                "abierta_desde": desde,
                "horas_abierta": round(horas, 2),
                "monto_apertura": a.monto_apertura,
                "efectivo_cobrado": cobrado,
                "movimientos_netos": movimientos,
                "efectivo_esperado": a.monto_apertura + cobrado + movimientos,
                "diferencia_apertura": a.diferencia_reportada,
            }
        )
    filas.sort(key=lambda f: f["horas_abierta"], reverse=True)
    return filas


def roles_contables() -> tuple[str, ...]:
    """Los roles que una categoría puede mapear a una cuenta (ADR-086).

    Vive acá porque el vocabulario es de contabilidad —qué papel juega una
    cuenta en un asiento— y lo consume `inventory`, que es donde la
    configuración se escribe. Que las dos listas no se separen lo fija un
    caso en `tests/test_contabilidad_por_categoria.py`.
    """
    return plantillas.ROLES


def problemas_de_config_contable(
    session: Session, empresa_id: uuid.UUID, config: dict[str, str] | None
) -> list[str]:
    """Qué está mal en el mapa de cuentas de una categoría, en castellano.

    Devuelve **mensajes** y no levanta: quien llama es `inventory`, y una
    excepción de `accounting` cruzando la frontera del módulo no la atrapa su
    manejador de errores — saldría como 500 en vez del 409 que corresponde.

    Comprueba las tres reglas que `_construir_lineas` ya impone al armar un
    asiento, adelantadas al momento de configurar: la cuenta existe **en esta
    empresa** (el PCGE se siembra por empresa), está activa, y es de último
    nivel. Imputar en el rubro que agrupa deja el mayor sin decir de qué se
    trata, y el rubro con movimiento propio además del de sus divisionarias.

    Dos consultas para todo el mapa, no dos por rol.
    """
    if not config:
        return []
    codigos = sorted({codigo for codigo in config.values() if codigo})
    if not codigos:
        return []

    repo = CuentaContableRepo(session)
    cuentas = repo.get_by_codigos(empresa_id, codigos)
    # Un solo viaje para saber cuáles agrupan a otras: `tiene_hijas` por
    # código serían N consultas para un formulario de siete campos.
    con_hijas = {
        padre_id
        for padre_id in session.scalars(
            select(CuentaContable.cuenta_padre_id).where(
                CuentaContable.empresa_id == empresa_id,
                CuentaContable.cuenta_padre_id.is_not(None),
                CuentaContable.deleted_at.is_(None),
            )
        ).all()
    }

    problemas = []
    for rol, codigo in sorted(config.items()):
        if not codigo:
            continue
        cuenta = cuentas.get(codigo)
        if cuenta is None:
            problemas.append(f"{rol}: la cuenta {codigo} no existe en el plan de la empresa")
        elif not cuenta.activa:
            problemas.append(f"{rol}: la cuenta {codigo} está inactiva")
        elif cuenta.id in con_hijas:
            problemas.append(
                f"{rol}: la cuenta {codigo} agrupa a otras; el asiento se "
                "imputa en una de último nivel"
            )
    return problemas


def cuentas_por_codigo(
    session: Session, empresa_id: uuid.UUID, codigos: list[str]
) -> dict[str, uuid.UUID]:
    """`codigo` → `cuenta_contable.id`, para los códigos que existan y estén
    activos. Los que no, simplemente no aparecen: quien llama decide si eso
    es un error o un motivo para caer al default."""
    if not codigos:
        return {}
    return {
        codigo: cuenta.id
        for codigo, cuenta in CuentaContableRepo(session)
        .get_by_codigos(empresa_id, codigos)
        .items()
        if cuenta.activa
    }

