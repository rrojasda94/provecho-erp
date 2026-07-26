"""Emisión del comprobante electrónico de una venta (boleta / factura).

Dos pasos deliberadamente separados: al cobrar se crea el `comprobante`
en estado `pendiente` (rápido, dentro de la transacción de la venta), y el
envío a Factiliza corre en la cola. Una caída del proveedor deja el
comprobante pendiente de reintento, nunca bloquea la caja (RN-COM-003).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.events import event_bus
from src.modules.sales.application.errors import Conflicto, NoEncontrado
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Venta
from src.modules.sales.infrastructure.repositories import (
    ClienteRepo,
    ComprobanteRepo,
    ProductoComercialRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.shared.integrations import factiliza
from src.shared.models import Comprobante

MAX_INTENTOS_EMISION = 5


def emision_habilitada() -> bool:
    """Sin token configurado no hay facturación electrónica: el ERP sigue
    operando y los comprobantes quedan pendientes."""
    return bool(settings.factiliza_token)


def crear_comprobante_pendiente(session: Session, venta: Venta) -> Comprobante | None:
    """Idempotente por venta: cobrar dos veces no duplica el comprobante."""
    repo = ComprobanteRepo(session)
    existente = repo.por_venta(venta.id)
    if existente is not None:
        return existente

    punto_venta = PuntoVentaRepo(session).get(venta.punto_venta_id)
    if punto_venta is None:
        raise NoEncontrado("punto de venta no encontrado")
    empresa = repo.empresa_de_sucursal(venta.sucursal_id)
    if empresa is None:
        raise NoEncontrado("empresa de la sucursal no encontrada")

    cliente = ClienteRepo(session).get(venta.cliente_id) if venta.cliente_id else None
    tipo = rules.tipo_comprobante(cliente.tipo if cliente else None,
                                  cliente.ruc if cliente else None)
    serie = punto_venta.serie_factura if tipo == "factura" else punto_venta.serie_boleta

    comprobante = Comprobante(
        empresa_id=empresa.id,
        venta_id=venta.id,
        punto_venta_id=punto_venta.id,
        direccion="emitido",
        tipo=tipo,
        serie=serie,
        correlativo=repo.siguiente_correlativo(empresa.id, serie),
        sustento="voucher_medio_pago",
        idempotency_key=f"venta:{venta.id}",
        estado_emision="pendiente",
    )
    session.add(comprobante)
    session.flush()
    return comprobante


def _documento(session: Session, comprobante: Comprobante) -> factiliza.Documento:
    repo = ComprobanteRepo(session)
    empresa = repo.empresa(comprobante.empresa_id)
    venta = VentaRepo(session).get(comprobante.venta_id)
    cliente = ClienteRepo(session).get(venta.cliente_id) if venta.cliente_id else None
    productos = ProductoComercialRepo(session)

    items = []
    for it in VentaRepo(session).items(venta.id):
        prod = productos.get(it.producto_comercial_id)
        # El descuento se reparte en el precio unitario: el endpoint de
        # Factiliza no recibe descuento por línea.
        neto = rules.precio_unitario_neto(it.cantidad, it.precio_unitario, it.descuento)
        items.append(
            factiliza.Item(
                codigo=str(prod.id) if prod else str(it.producto_comercial_id),
                descripcion=prod.nombre if prod else "PRODUCTO",
                cantidad=it.cantidad,
                precio_unitario=neto,
            )
        )

    return factiliza.Documento(
        empresa_ruc=empresa.ruc,
        tipo_doc=(
            factiliza.TIPO_DOC_FACTURA
            if comprobante.tipo == "factura"
            else factiliza.TIPO_DOC_BOLETA
        ),
        serie=comprobante.serie,
        correlativo=comprobante.correlativo,
        fecha_emision=datetime.now(UTC),
        cliente=_cliente_para_sunat(session, cliente),
        items=items,
        # Ley 27037: las empresas de Amazonía venden exoneradas de IGV
        # (RN-IMP-001). El régimen lo declara la empresa, no la venta.
        exonerado_igv=empresa.zona_tributaria == "amazonia_ley27037",
        igv_porcentaje=settings.igv_porcentaje,
    )


def _cliente_para_sunat(session: Session, cliente) -> factiliza.Cliente:
    """Cliente anónimo es válido en boleta (RN-PER-005)."""
    if cliente is None:
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_SIN_DOCUMENTO,
            num_doc="00000000",
            razon_social="CLIENTES VARIOS",
        )
    if cliente.tipo == "juridico":
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_RUC,
            num_doc=cliente.ruc or "",
            razon_social=cliente.razon_social or "",
            direccion=cliente.contacto or "-",
        )
    persona = ComprobanteRepo(session).persona(cliente.persona_id)
    if persona is None:
        return factiliza.Cliente(
            tipo_doc=rules.DOC_SUNAT_SIN_DOCUMENTO,
            num_doc="00000000",
            razon_social="CLIENTES VARIOS",
        )
    return factiliza.Cliente(
        tipo_doc=rules.doc_sunat_de_persona(persona.tipo_documento),
        num_doc=persona.numero_documento,
        razon_social=f"{persona.nombres} {persona.apellidos}".strip(),
        direccion=persona.domicilio or "-",
    )


def emitir_comprobante(
    session: Session,
    comprobante_id: uuid.UUID,
    client: factiliza.FactilizaClient | None = None,
) -> Comprobante:
    """Envía a Factiliza y persiste el veredicto de SUNAT.

    Levanta `FactilizaError` ante fallo de transporte para que la cola
    reintente; un rechazo de SUNAT no es excepción, es un veredicto.
    """
    comprobante = ComprobanteRepo(session).get(comprobante_id)
    if comprobante is None:
        raise NoEncontrado("comprobante no encontrado")
    if comprobante.estado_emision == "aceptado":
        return comprobante
    if comprobante.direccion != "emitido":
        raise Conflicto("solo se emite un comprobante propio, no uno recibido")
    if comprobante.intentos_emision >= MAX_INTENTOS_EMISION:
        raise Conflicto(
            f"comprobante agotó {MAX_INTENTOS_EMISION} intentos; requiere revisión manual"
        )

    comprobante.intentos_emision += 1
    payload = factiliza.construir_payload(_documento(session, comprobante))
    respuesta = (client or factiliza.FactilizaClient()).enviar_comprobante(payload)

    comprobante.respuesta_proveedor = respuesta.crudo
    comprobante.detalle_emision = respuesta.mensaje[:1000] if respuesta.mensaje else None
    if not respuesta.aceptado:
        comprobante.estado_emision = "rechazado"
        return comprobante

    comprobante.estado_emision = "aceptado"
    comprobante.hash_proveedor = respuesta.hash
    venta = VentaRepo(session).get(comprobante.venta_id)
    if venta is not None and venta.estado == "pagada":
        venta.estado = "facturada"
    event_bus.publish(
        "sales.comprobante_emitido",
        {
            "comprobante_id": str(comprobante.id),
            "venta_id": str(comprobante.venta_id),
            "empresa_id": str(comprobante.empresa_id),
            "tipo": comprobante.tipo,
            "serie_numero": f"{comprobante.serie}-{comprobante.correlativo:08d}",
            "total": str(venta.total if venta else Decimal(0)),
        },
    )
    return comprobante
