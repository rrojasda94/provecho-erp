"""Nota de crédito: corregir una venta ya cobrada (RN-CPP-009).

Nunca toca la red — el cliente de Factiliza se reemplaza por un doble.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import comprobantes, notas_credito, ventas
from src.modules.sales.application.errors import Conflicto, ReglaNegocio
from src.modules.sales.infrastructure.models import MedioPago
from src.modules.sales.infrastructure.repositories import VentaRepo
from src.shared.integrations import factiliza
from src.shared.integrations.factiliza import RespuestaEmision
from tests.conftest import abrir_caja_directa
from tests.test_venta_slice import _crear_cadena_base, _crear_trabajador


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class _ClienteFalso:
    """Doble del cliente HTTP: guarda los payloads para poder afirmarlos."""

    def __init__(self, respuesta=None) -> None:
        self.respuesta = respuesta or _aceptado()
        self.payloads: list[dict] = []

    def enviar_comprobante(self, payload: dict) -> RespuestaEmision:
        self.payloads.append(payload)
        return self.respuesta

    def enviar_nota_credito(self, payload: dict) -> RespuestaEmision:
        self.payloads.append(payload)
        return self.respuesta


def _aceptado() -> RespuestaEmision:
    return RespuestaEmision(
        aceptado=True,
        codigo_sunat="0",
        mensaje="aceptada",
        hash="AeOqQVd8d5kfPS+CmeCMF+NNMpI=",
        crudo={"status": 200, "success": True},
    )


def _rechazado() -> RespuestaEmision:
    return RespuestaEmision(
        aceptado=False,
        codigo_sunat="2335",
        mensaje="documento afectado no existe",
        hash=None,
        crudo={"status": 400, "success": False},
    )


@pytest.fixture
def venta_facturada(session, monkeypatch):
    """Venta cobrada con su comprobante ya aceptado por SUNAT."""
    monkeypatch.setattr(comprobantes, "emision_habilitada", lambda: True)
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    punto_venta.serie_nc_boleta = "BC01"
    punto_venta.serie_nc_factura = "FC01"
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000001")
    medio = MedioPago(
        empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo"
    )
    session.add(medio)
    session.flush()
    abrir_caja_directa(session, punto_venta_id=punto_venta.id, cajero_id=usuario.id)

    venta = ventas.crear_venta(
        session,
        sucursal_id=sucursal.id,
        punto_venta_id=punto_venta.id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=usuario.id,
        idempotency_key="venta-nc-1",
        items=[
            {
                "producto_comercial_id": producto.id,
                "cantidad": 3,
                "precio_unitario": Decimal("50.00"),
            }
        ],
    )
    _pago, venta, comprobante = ventas.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=medio.id,
        monto=Decimal("150.00"),
        idempotency_key="pago-nc-1",
    )
    comprobantes.emitir_comprobante(session, comprobante.id, client=_ClienteFalso())
    session.flush()
    return venta, comprobante, usuario


# --- Payload ------------------------------------------------------------------
def test_el_payload_declara_documento_afectado_y_motivo() -> None:
    """Sin `afectado_*` y `motivo_Cod` la nota no es una nota: SUNAT la
    rechaza y contablemente no dice nada."""
    doc = factiliza.Documento(
        empresa_ruc="20450311520",
        tipo_doc=factiliza.TIPO_DOC_NOTA_CREDITO,
        serie="BC01",
        correlativo=1,
        fecha_emision=__import__("datetime").datetime(2026, 8, 4),
        cliente=factiliza.Cliente("0", "00000000", "CLIENTES VARIOS"),
        items=[factiliza.Item("P001", "PIZZA", Decimal(1), Decimal("118.00"))],
        exonerado_igv=False,
    )
    payload = factiliza.construir_payload_nota_credito(
        doc,
        factiliza.DocumentoAfectado(factiliza.TIPO_DOC_BOLETA, "B001", 7),
        factiliza.MOTIVO_NC_ANULACION,
    )
    assert payload["tipo_Doc"] == factiliza.TIPO_DOC_NOTA_CREDITO
    assert payload["afectado_Tipo_Doc"] == factiliza.TIPO_DOC_BOLETA
    assert payload["afectado_Num_Doc"] == "B001-7"
    assert payload["motivo_Cod"] == "01"
    assert payload["motivo_Descripcion"] == "Anulación de la operación"
    # Una nota no cobra: mandar forma de pago confunde la lectura del XML.
    assert "forma_pago" not in payload
    # La aritmética sigue siendo la del comprobante: S/118 = 100 + 18.
    assert payload["monto_Oper_Gravadas"] == 100.00
    assert payload["monto_Igv"] == 18.00


def test_un_motivo_fuera_del_catalogo_no_se_envia() -> None:
    doc = factiliza.Documento(
        empresa_ruc="20450311520",
        tipo_doc=factiliza.TIPO_DOC_NOTA_CREDITO,
        serie="BC01",
        correlativo=1,
        fecha_emision=__import__("datetime").datetime(2026, 8, 4),
        cliente=factiliza.Cliente("0", "00000000", "CLIENTES VARIOS"),
        items=[factiliza.Item("P001", "PIZZA", Decimal(1), Decimal("10.00"))],
        exonerado_igv=False,
    )
    with pytest.raises(ValueError, match="catálogo 09"):
        factiliza.construir_payload_nota_credito(
            doc, factiliza.DocumentoAfectado("03", "B001", 1), "99"
        )


# --- Nota total ---------------------------------------------------------------
def test_nota_total_anula_la_venta_y_el_comprobante(session, venta_facturada):
    venta, comprobante, usuario = venta_facturada
    cliente = _ClienteFalso()

    nota = notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_ANULACION,
        emitido_por=usuario.id,
        client=cliente,
    )

    assert nota.tipo == "nc"
    assert nota.serie == "BC01"
    assert nota.estado_emision == "aceptado"
    assert nota.afecta_comprobante_id == comprobante.id
    assert nota.detalle_nc is None  # total
    assert comprobante.anulado_por_nc_id == nota.id
    assert venta.estado == "anulada"
    # El documento afectado viaja con serie y correlativo del original.
    assert cliente.payloads[-1]["afectado_Num_Doc"] == f"B001-{comprobante.correlativo}"


def test_la_nota_usa_la_serie_propia_y_su_propio_correlativo(session, venta_facturada):
    """Numerar la nota en la serie de la boleta es rechazo de SUNAT."""
    _venta, comprobante, usuario = venta_facturada
    nota = notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_ANULACION,
        emitido_por=usuario.id,
        client=_ClienteFalso(),
    )
    assert nota.serie == "BC01" != comprobante.serie
    assert nota.correlativo == 1


def test_sin_serie_de_nota_configurada_no_se_emite(session, venta_facturada):
    _venta, comprobante, usuario = venta_facturada
    from src.modules.sales.infrastructure.repositories import PuntoVentaRepo

    PuntoVentaRepo(session).get(comprobante.punto_venta_id).serie_nc_boleta = None

    with pytest.raises(Conflicto, match="serie de nota de crédito"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo=factiliza.MOTIVO_NC_ANULACION,
            emitido_por=usuario.id,
            client=_ClienteFalso(),
        )


# --- Nota parcial -------------------------------------------------------------
def test_nota_parcial_acredita_solo_lo_devuelto_y_no_anula_la_venta(
    session, venta_facturada
):
    venta, comprobante, usuario = venta_facturada
    linea = VentaRepo(session).items(venta.id)[0]
    cliente = _ClienteFalso()

    nota = notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_DEVOLUCION_POR_ITEM,
        emitido_por=usuario.id,
        detalle=[{"venta_item_id": str(linea.id), "cantidad": "1"}],
        client=cliente,
    )

    assert nota.detalle_nc == [{"venta_item_id": str(linea.id), "cantidad": "1"}]
    # La venta sigue viva: se devolvió 1 de 3.
    assert venta.estado != "anulada"
    assert comprobante.anulado_por_nc_id is None
    # Y la nota factura solo esa unidad, no las tres.
    assert cliente.payloads[-1]["detalle"][0]["cantidad"] == 1.0


def test_no_se_puede_acreditar_mas_de_lo_vendido(session, venta_facturada):
    venta, comprobante, usuario = venta_facturada
    linea = VentaRepo(session).items(venta.id)[0]

    with pytest.raises(ReglaNegocio, match="solo quedan"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo=factiliza.MOTIVO_NC_DEVOLUCION_POR_ITEM,
            emitido_por=usuario.id,
            detalle=[{"venta_item_id": str(linea.id), "cantidad": "4"}],
            client=_ClienteFalso(),
        )


def test_dos_notas_parciales_no_acreditan_dos_veces_la_misma_unidad(
    session, venta_facturada
):
    """La segunda devolución cuenta contra lo que quedaba, no contra lo
    vendido: si no, devolver 2 y después 2 de 3 pasaría."""
    venta, comprobante, usuario = venta_facturada
    linea = VentaRepo(session).items(venta.id)[0]
    detalle = [{"venta_item_id": str(linea.id), "cantidad": "2"}]

    notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_DEVOLUCION_POR_ITEM,
        emitido_por=usuario.id,
        detalle=detalle,
        client=_ClienteFalso(),
    )
    session.flush()

    with pytest.raises(ReglaNegocio, match="solo quedan"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo=factiliza.MOTIVO_NC_DEVOLUCION_POR_ITEM,
            emitido_por=usuario.id,
            detalle=detalle,
            client=_ClienteFalso(),
        )


# --- Reglas de emisión --------------------------------------------------------
def test_no_se_acredita_un_comprobante_que_sunat_no_acepto(session, venta_facturada):
    """Un comprobante rechazado no existe para SUNAT: si está mal, se
    corrige antes de emitirlo, no con una nota."""
    _venta, comprobante, usuario = venta_facturada
    comprobante.estado_emision = "rechazado"

    with pytest.raises(Conflicto, match="aceptado"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo=factiliza.MOTIVO_NC_ANULACION,
            emitido_por=usuario.id,
            client=_ClienteFalso(),
        )


def test_no_se_acredita_dos_veces_el_mismo_comprobante(session, venta_facturada):
    _venta, comprobante, usuario = venta_facturada
    notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_ANULACION,
        emitido_por=usuario.id,
        client=_ClienteFalso(),
    )
    session.flush()

    with pytest.raises(Conflicto, match="ya fue anulado"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo=factiliza.MOTIVO_NC_ANULACION,
            emitido_por=usuario.id,
            client=_ClienteFalso(),
        )


def test_una_nota_rechazada_no_anula_nada(session, venta_facturada):
    """El rechazo es un veredicto, no un error de transporte: la nota queda
    registrada con su motivo y la venta sigue como estaba."""
    venta, comprobante, usuario = venta_facturada

    nota = notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_ANULACION,
        emitido_por=usuario.id,
        client=_ClienteFalso(_rechazado()),
    )

    assert nota.estado_emision == "rechazado"
    assert nota.detalle_emision == "documento afectado no existe"
    assert comprobante.anulado_por_nc_id is None
    assert venta.estado != "anulada"


def test_una_nota_de_correccion_no_anula_la_venta(session, venta_facturada):
    """Error en el RUC: la operación ocurrió, el papel estaba mal. El
    comprobante queda anulado para reemitir el corregido, la venta no."""
    venta, comprobante, usuario = venta_facturada

    nota = notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo="02",
        emitido_por=usuario.id,
        repone_stock=False,
        client=_ClienteFalso(),
    )

    assert comprobante.anulado_por_nc_id == nota.id
    assert venta.estado != "anulada"


def test_motivo_fuera_del_catalogo_se_rechaza_antes_de_emitir(session, venta_facturada):
    _venta, comprobante, usuario = venta_facturada
    with pytest.raises(ReglaNegocio, match="catálogo 09"):
        notas_credito.emitir_nota_credito(
            session,
            comprobante.id,
            motivo="99",
            emitido_por=usuario.id,
            client=_ClienteFalso(),
        )


# --- Reposición de stock ------------------------------------------------------
def test_el_evento_lleva_los_items_solo_si_se_pidio_reponer(session, venta_facturada):
    """`repone_stock` es de quien emite: en cocina el plato devuelto rara vez
    devuelve el insumo, y corregir un RUC no toca el inventario."""
    from src.core.events import event_bus

    _venta, comprobante, usuario = venta_facturada
    capturados: list[dict] = []
    event_bus.subscribe("sales.nota_credito_emitida", capturados.append)

    notas_credito.emitir_nota_credito(
        session,
        comprobante.id,
        motivo=factiliza.MOTIVO_NC_ANULACION,
        emitido_por=usuario.id,
        repone_stock=False,
        client=_ClienteFalso(),
    )
    session.commit()

    assert capturados[-1]["items"] == []
    assert capturados[-1]["repone_stock"] is False
    assert capturados[-1]["total"] is True


# --- Descarga de PDF / XML / CDR ----------------------------------------------
class _ClienteDescarga:
    def __init__(self) -> None:
        self.pedidos: list[tuple] = []

    def descargar(self, formato, tipo_doc, serie, correlativo):
        self.pedidos.append((formato, tipo_doc, serie, correlativo))
        return factiliza.DocumentoDescargado(
            formato=formato,
            contenido=b"%PDF-1.4 fake",
            content_type=factiliza.CONTENT_TYPES[formato],
            nombre_archivo=f"{serie}-{correlativo:08d}.{formato}",
        )


def test_se_descarga_el_documento_de_un_comprobante_aceptado(session, venta_facturada):
    _venta, comprobante, _usuario = venta_facturada
    cliente = _ClienteDescarga()

    doc = comprobantes.descargar_documento(session, comprobante.id, "xml", cliente)

    assert doc.content_type == "application/xml"
    assert doc.contenido == b"%PDF-1.4 fake"
    # Pide el tipo de documento en el catálogo de SUNAT, no el nombre interno.
    assert cliente.pedidos[-1][:2] == ("xml", factiliza.TIPO_DOC_BOLETA)


def test_no_se_descarga_lo_que_sunat_no_acepto(session, venta_facturada):
    """Antes de la aceptación no hay XML firmado ni CDR, y el PDF sería de un
    documento que SUNAT no reconoce."""
    _venta, comprobante, _usuario = venta_facturada
    comprobante.estado_emision = "pendiente"

    with pytest.raises(Conflicto, match="sin aceptación"):
        comprobantes.descargar_documento(session, comprobante.id, "pdf", _ClienteDescarga())


def test_formato_desconocido_se_rechaza(session, venta_facturada):
    _venta, comprobante, _usuario = venta_facturada
    with pytest.raises(ReglaNegocio, match="no descargable"):
        comprobantes.descargar_documento(session, comprobante.id, "docx", _ClienteDescarga())
