"""Casos de uso: asiento contable. Manual (permiso `accounting.asiento_manual`,
RN-CTB-001 cuadre) y automático (generado por `application/listeners.py` desde
un evento operativo mapeado en `regla_asiento`). Anular NUNCA borra/edita —
crea el asiento inverso en el periodo abierto vigente (RN-CTB-002)."""

import logging
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
from src.modules.inventory.application.queries_publicas import (
    config_contable_de_categorias,
)
from src.modules.users.infrastructure.models import Empresa
from src.shared import fechas, tributos

log = logging.getLogger(__name__)


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


def _config_utilizable(
    session: Session,
    empresa_id: uuid.UUID,
    config: dict[uuid.UUID, dict[str, str]],
) -> dict[uuid.UUID, dict[str, str]]:
    """Saca del mapa las cuentas que ya no sirven, y lo deja anotado.

    La validación al guardar (`inventory.catalogo`) es la primera barrera;
    esta es la segunda, para lo que cambió después: una cuenta desactivada o
    borrada del plan. Cae al código de fábrica de la línea en vez de dejar a
    la empresa sin poder comprar — que es el mismo criterio no bloqueante con
    el que este módulo trata todo lo demás.

    Una consulta para todos los códigos de todas las categorías del evento.
    """
    codigos = sorted({c for mapa in config.values() for c in mapa.values() if c})
    if not codigos:
        return config
    validas = {
        codigo
        for codigo, cuenta in CuentaContableRepo(session)
        .get_by_codigos(empresa_id, codigos)
        .items()
        if cuenta.activa
    }
    descartadas = set(codigos) - validas
    if descartadas:
        log.warning(
            "cuentas configuradas en categorías que no existen o están "
            "inactivas en la empresa %s: %s — se usa el código de fábrica",
            empresa_id,
            ", ".join(sorted(descartadas)),
        )
    return {
        categoria_id: {rol: c for rol, c in mapa.items() if c in validas}
        for categoria_id, mapa in config.items()
    }


def _grupos_del_desglose(desglose: list[dict] | None) -> list[dict]:
    """Agrupa el desglose por `(categoria_id, es_servicio)` sumando montos.

    Dos líneas de la misma categoría producen **una** parte, no dos: el
    asiento habla de cuentas, no de líneas del documento.
    """
    if not desglose:
        return []
    sumado: dict[tuple, Decimal] = {}
    for entrada in desglose:
        monto = Decimal(str(entrada.get("monto") or 0))
        if monto <= 0:
            continue
        clave = (entrada.get("categoria_id"), bool(entrada.get("es_servicio")))
        sumado[clave] = sumado.get(clave, Decimal(0)) + monto
    return [
        {"categoria_id": categoria_id, "es_servicio": es_servicio, "monto": monto}
        for (categoria_id, es_servicio), monto in sumado.items()
    ]


def _codigo_del_rol(
    linea: plantillas_pcge.LineaPlantilla, grupo: dict, config: dict[str, str]
) -> str | None:
    """Qué cuenta usa esta línea para este grupo. `None` = la línea no se
    escribe para él.

    Un servicio no entra a ningún almacén: su parte omite el bloque de
    destino (`existencia` y `variacion_existencia`) y manda su compra a la
    63x. El asiento sigue cuadrando porque ese bloque es un débito y un
    crédito **del mismo importe**: quitarlos juntos no mueve la balanza.
    """
    rol = linea.rol
    if grupo["es_servicio"]:
        if rol in ("existencia", "variacion_existencia"):
            return None
        if rol == "compra":
            return config.get("servicio") or plantillas_pcge.CODIGO_SERVICIO_DE_FABRICA
    return config.get(rol) or linea.codigo


def _repartir_por_categoria(
    session: Session,
    empresa_id: uuid.UUID,
    plantilla: plantillas_pcge.Plantilla,
    importes: dict[str, Decimal],
    desglose: list[dict] | None,
) -> dict[tuple[str, str], Decimal]:
    """`(codigo, debe|haber)` → importe, ya repartido por categoría.

    Sin desglose útil —o si ninguna categoría configuró nada— devuelve
    exactamente lo que la plantilla dice, que es el comportamiento anterior a
    ADR-086. Esa ruta de escape es lo que hace el cambio retrocompatible.

    Dos categorías que resuelven al mismo código producen **una** línea: el
    mayor no gana nada con la misma cuenta escrita dos veces.
    """
    grupos = _grupos_del_desglose(desglose)
    config = (
        _config_utilizable(
            session,
            empresa_id,
            config_contable_de_categorias(
                session, empresa_id, [g["categoria_id"] for g in grupos]
            ),
        )
        if grupos
        else {}
    )
    hay_algo_que_repartir = any(linea.rol for linea in plantilla.lineas) and (
        any(config.get(g["categoria_id"]) for g in grupos)
        or any(g["es_servicio"] for g in grupos)
    )

    por_codigo: dict[tuple[str, str], Decimal] = {}

    def sumar(codigo: str, tipo: str, importe: Decimal) -> None:
        clave = (codigo, tipo)
        por_codigo[clave] = por_codigo.get(clave, Decimal(0)) + importe

    if not hay_algo_que_repartir:
        for linea in plantilla.lineas:
            sumar(linea.codigo, linea.tipo, importes[linea.importe])
        return por_codigo

    pesos = [g["monto"] for g in grupos]
    for linea in plantilla.lineas:
        importe = importes[linea.importe]
        if linea.rol is None or importe <= 0:
            sumar(linea.codigo, linea.tipo, importe)
            continue
        partes = plantillas_pcge.reparto_proporcional(importe, pesos)
        # El bloque de destino de un grupo de servicio no se escribe, así que
        # su parte se descarta junto con la del par: `existencia` y
        # `variacion_existencia` son el mismo importe de los dos lados.
        for grupo, parte in zip(grupos, partes, strict=True):
            codigo = _codigo_del_rol(linea, grupo, config.get(grupo["categoria_id"], {}))
            if codigo is not None:
                sumar(codigo, linea.tipo, parte)
    return por_codigo


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
    desglose: list[dict] | None = None,
) -> Asiento | None:
    """Asiento del PCGE para el evento, si hay plantilla y la empresa tiene
    las cuentas.

    `gravado_igv` es la casilla del comprobante: `None` deja decidir al
    default de la empresa (`shared.tributos`). Solo llega en los eventos de
    comprobante — el resto no lo conoce, y por eso su asiento no lleva IGV.

    `desglose` es `[{categoria_id, monto, es_servicio}]` — de qué se compone
    el monto del evento (ADR-086). Se usa como **peso, nunca como importe**:
    el asiento siempre suma `monto`, aunque el desglose venga incompleto, con
    una categoría sin resolver o desactualizado. Sin desglose el asiento es
    exactamente el de siempre, byte por byte.

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
    por_codigo = _repartir_por_categoria(
        session, empresa_id, plantilla, importes, desglose
    )
    # Las claves son `(codigo, debe|haber)`: la misma cuenta puede caer de
    # los dos lados, y al plan de cuentas se le pregunta por código.
    codigos = sorted({codigo for codigo, _ in por_codigo})
    cuentas = CuentaContableRepo(session).get_by_codigos(empresa_id, codigos)
    if any(codigo not in cuentas for codigo in codigos):
        return None

    # Una línea en cero no se escribe: con IGV exonerado, el asiento de venta
    # es de dos líneas y no de tres con una que dice 0.00.
    lineas = [
        (cuentas[codigo].id, tipo, importe)
        for (codigo, tipo), importe in sorted(por_codigo.items())
        if importe > 0
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
    desglose: list[dict] | None = None,
) -> Asiento | None:
    """Genera el asiento del evento. Dos fuentes, en este orden:

    1. la `regla_asiento` vigente de la empresa, si la configuró — la empresa
       manda sobre el default de fábrica;
    2. la **plantilla del PCGE** (`domain/plantillas.py`), que es el asiento
       oficial peruano completo, con su desagregación de IGV y su asiento de
       destino.

    `None` si no hay ninguna de las dos (se omite y se audita en el log del
    llamador) — mismo criterio no bloqueante de siempre.

    `desglose` (ADR-086) **solo lo usa la plantilla**. La empresa que
    configuró una `regla_asiento` pidió un asiento de dos líneas: repartirlas
    por categoría sería pisarle la decisión que tomó a propósito.
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
            desglose=desglose,
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
