"""Guía de remisión: mercadería propia que viaja por la vía pública
(RN-GDR-001..003, RN-TRP-002).

Dos emisores, un solo documento: un **traslado entre almacenes** y —desde
2026-08-06— una **devolución a proveedor**. SUNAT no distingue el motivo
para exigir la guía; lo que cambia es a dónde va la carga y quién la
recibe.

Lo que hace que la guía signifique algo es que **no se teclea lo que
declara**: las líneas salen del documento que movió el stock
(`transferencia_item` o `devolucion_item`), que es el registro de lo que de
verdad se descontó del origen. RN-TRP-002 exige que lo transportado
coincida exactamente con lo declarado, y un formulario aparte es justamente
la forma de que no coincidan.

Lo que sí se teclea es lo que el sistema no puede saber: quién maneja, en
qué vehículo, cuánto pesa la carga y qué día arranca el viaje.

La emisión electrónica es asíncrona, igual que el comprobante (ADR-005): la
guía existe y se imprime apenas se crea; que SUNAT la acepte llega después
por la cola. Un camión no espera a un proveedor externo.
"""

import datetime
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.events import event_bus
from src.modules.inventory.application.errors import NoEncontrado, ReglaNegocio
from src.modules.inventory.infrastructure.models import (
    Articulo,
    GuiaRemision,
    GuiaRemisionItem,
    Sku,
    UnidadMedida,
)
from src.modules.inventory.infrastructure.repositories import (
    DevolucionRepo,
    GuiaRemisionRepo,
    TransferenciaRepo,
)
from src.modules.purchases.application.queries_publicas import proveedor_para_guia
from src.modules.users.infrastructure.models import Almacen, Empresa
from src.shared import fechas
from src.shared.integrations.factiliza import (
    FactilizaClient,
    FactilizaError,
)
from src.shared.integrations.factiliza import (
    guias as guias_mapper,
)

# Serie de guía de remisión electrónica: SUNAT las quiere empezando en `T`.
# Una sola serie por empresa mientras haya un almacén emisor; el día que
# emitan dos almacenes en paralelo, esto pasa a ser columna del almacén.
SERIE_GUIA = "T001"


def _exigir_transferencia_despachada(session: Session, transferencia_id: uuid.UUID):
    transferencia = TransferenciaRepo(session).get(transferencia_id)
    if transferencia is None:
        raise NoEncontrado("transferencia no encontrada")
    return transferencia


def _lineas_de_transferencia(
    session: Session, transferencia_id: uuid.UUID
) -> list[tuple[uuid.UUID, Decimal, str, str]]:
    """`(sku_id, cantidad, descripción, unidad SUNAT)` agrupado por SKU.

    Por SKU y no por lote: el despacho reparte por FEFO y una línea de 10 kg
    puede salir de tres lotes (ADR-015), pero eso es control interno. SUNAT
    declara producto y cantidad; la trazabilidad por lote sigue entera en
    `transferencia_item`, que es donde sirve.
    """
    items = TransferenciaRepo(session).items(transferencia_id)
    if not items:
        raise ReglaNegocio("la transferencia no tiene ítems que declarar")

    por_sku: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for item in items:
        por_sku[item.sku_id] += item.cantidad_enviada
    return [_linea(session, sku_id, cantidad) for sku_id, cantidad in por_sku.items()]


def _linea(
    session: Session, sku_id: uuid.UUID, cantidad: Decimal
) -> tuple[uuid.UUID, Decimal, str, str]:
    sku = session.get(Sku, sku_id)
    articulo = session.get(Articulo, sku.articulo_id) if sku else None
    if articulo is None:
        raise NoEncontrado(f"artículo del SKU {sku_id} no encontrado")
    udm = session.get(UnidadMedida, articulo.unidad_medida_id)
    return (
        sku_id,
        cantidad,
        articulo.nombre,
        guias_mapper.codigo_unidad(udm.nombre if udm else ""),
    )


def _lineas_de_devolucion(
    session: Session, devolucion_id: uuid.UUID
) -> list[tuple[uuid.UUID, Decimal, str, str]]:
    """Mismo criterio que el traslado: agrupado por SKU, sin el lote.

    El lote sigue en `devolucion_item` —y ahí es donde el proveedor lo
    necesita para el reclamo—; la guía declara producto y cantidad.
    """
    items = DevolucionRepo(session).items(devolucion_id)
    if not items:
        raise ReglaNegocio("la devolución no tiene ítems que declarar")
    por_sku: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for item in items:
        por_sku[item.sku_id] += item.cantidad
    return [_linea(session, sku_id, cantidad) for sku_id, cantidad in por_sku.items()]


def emitir_guia_de_devolucion(
    session: Session,
    devolucion_id: uuid.UUID,
    *,
    emitida_por: uuid.UUID,
    lugar_destino: str,
    chofer_nombres: str,
    chofer_apellidos: str,
    chofer_num_doc: str,
    chofer_licencia: str,
    vehiculo_placa: str,
    peso_bruto_kg: Decimal,
    fecha_inicio_traslado: datetime.date | None = None,
    modalidad_traslado: str = "02",
    observacion: str | None = None,
) -> GuiaRemision:
    """Guía de una devolución a proveedor.

    Motivo `13` (otros) del catálogo 20: SUNAT no tiene código propio para
    "devolución al proveedor", y usar `04` —traslado entre establecimientos
    de la misma empresa— sería declarar algo falso, porque el destino es de
    otro contribuyente.

    `lugar_destino` se teclea: `proveedor` no tiene dirección modelada, y
    esto cae en la misma categoría que el chofer y la placa —lo que el
    sistema no puede saber—. El RUC del receptor sí sale del proveedor, por
    el contrato público de `purchases`.
    """
    repo = GuiaRemisionRepo(session)
    existente = repo.de_devolucion(devolucion_id)
    if existente is not None:
        return existente

    devolucion = DevolucionRepo(session).get(devolucion_id)
    if devolucion is None:
        raise NoEncontrado("devolución no encontrada")
    if devolucion.origen != "proveedor":
        raise ReglaNegocio(
            "solo la devolución a proveedor emite guía: lo que devuelve un "
            "cliente no sale del almacén"
        )
    if devolucion.estado != "registrada":
        raise ReglaNegocio(f"la devolución está {devolucion.estado}")

    origen = session.get(Almacen, devolucion.almacen_id)
    if origen is None:
        raise NoEncontrado("almacén de origen no encontrado")
    empresa = session.get(Empresa, origen.empresa_id)
    if empresa is None:
        raise NoEncontrado("empresa del almacén no encontrada")
    if peso_bruto_kg <= 0:
        raise ReglaNegocio("el peso bruto declarado debe ser mayor que cero")

    proveedor = (
        proveedor_para_guia(session, devolucion.referencia_id)
        if devolucion.referencia_id
        else None
    )
    return _crear_guia(
        session,
        repo,
        empresa=empresa,
        lineas=_lineas_de_devolucion(session, devolucion_id),
        transferencia_id=None,
        devolucion_id=devolucion_id,
        ruc_receptor=(proveedor or {}).get("ruc") or empresa.ruc,
        lugar_origen=origen.direccion or origen.nombre,
        lugar_destino=lugar_destino.strip(),
        motivo_traslado="13",
        modalidad_traslado=modalidad_traslado,
        fecha_inicio_traslado=fecha_inicio_traslado,
        peso_bruto_kg=peso_bruto_kg,
        chofer_nombres=chofer_nombres,
        chofer_apellidos=chofer_apellidos,
        chofer_num_doc=chofer_num_doc,
        chofer_licencia=chofer_licencia,
        vehiculo_placa=vehiculo_placa,
        emitida_por=emitida_por,
        observacion=observacion,
    )


def emitir_guia(
    session: Session,
    transferencia_id: uuid.UUID,
    *,
    emitida_por: uuid.UUID,
    chofer_nombres: str,
    chofer_apellidos: str,
    chofer_num_doc: str,
    chofer_licencia: str,
    vehiculo_placa: str,
    peso_bruto_kg: Decimal,
    fecha_inicio_traslado: datetime.date | None = None,
    motivo_traslado: str = "04",
    modalidad_traslado: str = "02",
    observacion: str | None = None,
) -> GuiaRemision:
    """Emite la guía de un traslado ya despachado.

    Idempotente por transferencia: pedirla dos veces devuelve la misma guía
    en vez de numerar una segunda. Dos guías del mismo traslado declararían
    la misma mercadería dos veces, que ante SUNAT es exactamente lo que no
    se puede hacer.
    """
    transferencia = _exigir_transferencia_despachada(session, transferencia_id)

    repo = GuiaRemisionRepo(session)
    existente = repo.de_transferencia(transferencia_id)
    if existente is not None:
        return existente

    origen = session.get(Almacen, transferencia.origen_almacen_id)
    destino = session.get(Almacen, transferencia.destino_almacen_id)
    if origen is None or destino is None:
        raise NoEncontrado("almacén de origen o destino no encontrado")
    empresa = session.get(Empresa, origen.empresa_id)
    if empresa is None:
        raise NoEncontrado("empresa del almacén no encontrada")
    if peso_bruto_kg <= 0:
        raise ReglaNegocio("el peso bruto declarado debe ser mayor que cero")

    return _crear_guia(
        session,
        repo,
        empresa=empresa,
        lineas=_lineas_de_transferencia(session, transferencia_id),
        transferencia_id=transferencia_id,
        devolucion_id=None,
        # Traslado entre establecimientos propios: emisor y receptor son la
        # misma empresa, y que coincidan es lo que sustenta el motivo `04`.
        ruc_receptor=empresa.ruc,
        lugar_origen=origen.direccion or origen.nombre,
        lugar_destino=destino.direccion or destino.nombre,
        motivo_traslado=motivo_traslado,
        modalidad_traslado=modalidad_traslado,
        fecha_inicio_traslado=fecha_inicio_traslado,
        peso_bruto_kg=peso_bruto_kg,
        chofer_nombres=chofer_nombres,
        chofer_apellidos=chofer_apellidos,
        chofer_num_doc=chofer_num_doc,
        chofer_licencia=chofer_licencia,
        vehiculo_placa=vehiculo_placa,
        emitida_por=emitida_por,
        observacion=observacion,
    )


def _crear_guia(
    session: Session,
    repo: GuiaRemisionRepo,
    *,
    empresa,
    lineas,
    transferencia_id,
    devolucion_id,
    ruc_receptor,
    lugar_origen,
    lugar_destino,
    motivo_traslado,
    modalidad_traslado,
    fecha_inicio_traslado,
    peso_bruto_kg,
    chofer_nombres,
    chofer_apellidos,
    chofer_num_doc,
    chofer_licencia,
    vehiculo_placa,
    emitida_por,
    observacion,
) -> GuiaRemision:
    """Numera, arma las líneas y avisa. Lo común a los dos emisores: lo que
    cambia entre un traslado y una devolución es a dónde va y quién recibe,
    no cómo se emite el documento."""
    guia = repo.add(
        GuiaRemision(
            empresa_id=empresa.id,
            transferencia_id=transferencia_id,
            devolucion_id=devolucion_id,
            serie=SERIE_GUIA,
            correlativo=repo.siguiente_correlativo(empresa.id, SERIE_GUIA),
            fecha_inicio_traslado=fecha_inicio_traslado or fechas.hoy(),
            motivo_traslado=motivo_traslado,
            modalidad_traslado=modalidad_traslado,
            peso_bruto_kg=peso_bruto_kg,
            ruc_emisor=empresa.ruc,
            ruc_receptor=ruc_receptor,
            lugar_origen=lugar_origen,
            lugar_destino=lugar_destino,
            chofer_nombres=chofer_nombres.strip(),
            chofer_apellidos=chofer_apellidos.strip(),
            chofer_num_doc=chofer_num_doc.strip(),
            chofer_licencia=chofer_licencia.strip(),
            vehiculo_placa=vehiculo_placa.strip().upper(),
            emitida_por=emitida_por,
            observacion=observacion,
            estado_emision="pendiente",
        )
    )
    for sku_id, cantidad, descripcion, unidad in lineas:
        repo.add_item(
            GuiaRemisionItem(
                guia_remision_id=guia.id,
                sku_id=sku_id,
                cantidad=cantidad,
                descripcion=descripcion,
                unidad=unidad,
            )
        )

    event_bus.publish(
        "inventory.guia_remision_emitida",
        {
            "guia_remision_id": str(guia.id),
            "transferencia_id": str(transferencia_id) if transferencia_id else None,
            "devolucion_id": str(devolucion_id) if devolucion_id else None,
            "serie": guia.serie,
            "correlativo": guia.correlativo,
        },
        session=session,
    )
    return guia


def enviar_a_sunat(session: Session, guia_id: uuid.UUID) -> GuiaRemision:
    """Manda la guía al proveedor y guarda el veredicto.

    Un **rechazo es una respuesta del negocio**, no un error: la guía queda
    `rechazado` con su motivo y alguien tiene que corregir el dato. Solo un
    fallo de transporte levanta `FactilizaError`, que es lo único que vale
    la pena reintentar.
    """
    repo = GuiaRemisionRepo(session)
    guia = repo.get(guia_id)
    if guia is None:
        raise NoEncontrado("guía de remisión no encontrada")
    if guia.estado_emision == "aceptado":
        return guia

    payload = guias_mapper.construir_payload_guia(
        guias_mapper.Guia(
            empresa_ruc=guia.ruc_emisor,
            serie=guia.serie,
            correlativo=guia.correlativo,
            fecha_emision=guia.created_at or datetime.datetime.now(datetime.UTC),
            fecha_inicio_traslado=guia.fecha_inicio_traslado,
            motivo_traslado=guia.motivo_traslado,
            modalidad_traslado=guia.modalidad_traslado,
            peso_bruto_kg=guia.peso_bruto_kg,
            receptor_ruc=guia.ruc_receptor,
            lugar_origen=guia.lugar_origen,
            lugar_destino=guia.lugar_destino,
            chofer_nombres=guia.chofer_nombres,
            chofer_apellidos=guia.chofer_apellidos,
            chofer_num_doc=guia.chofer_num_doc,
            chofer_licencia=guia.chofer_licencia,
            vehiculo_placa=guia.vehiculo_placa,
            items=[
                guias_mapper.ItemGuia(
                    codigo=str(item.sku_id),
                    descripcion=item.descripcion,
                    cantidad=item.cantidad,
                    unidad=item.unidad,
                )
                for item in repo.items(guia.id)
            ],
        )
    )

    guia.intentos_emision += 1
    try:
        respuesta = FactilizaClient().enviar_guia_remision(payload)
    except FactilizaError as e:
        guia.estado_emision = "error"
        guia.detalle_emision = str(e)
        raise

    guia.estado_emision = "aceptado" if respuesta.aceptado else "rechazado"
    guia.hash_proveedor = respuesta.hash
    guia.detalle_emision = respuesta.mensaje
    guia.respuesta_proveedor = respuesta.crudo
    event_bus.publish(
        "inventory.guia_remision_emitida_sunat",
        {
            "guia_remision_id": str(guia.id),
            "estado_emision": guia.estado_emision,
            "codigo_sunat": respuesta.codigo_sunat,
        },
        session=session,
    )
    return guia


def detalle(
    session: Session, guia_id: uuid.UUID
) -> tuple[GuiaRemision, list[GuiaRemisionItem]]:
    repo = GuiaRemisionRepo(session)
    guia = repo.get(guia_id)
    if guia is None:
        raise NoEncontrado("guía de remisión no encontrada")
    return guia, repo.items(guia_id)


def de_transferencia(session: Session, transferencia_id: uuid.UUID) -> GuiaRemision:
    guia = GuiaRemisionRepo(session).de_transferencia(transferencia_id)
    if guia is None:
        raise NoEncontrado("esa transferencia todavía no tiene guía de remisión")
    return guia


def q_listar(
    session: Session,
    *,
    empresa_id: uuid.UUID | None = None,
    estado_emision: str | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return GuiaRemisionRepo(session).q_list(empresa_id, estado_emision)
