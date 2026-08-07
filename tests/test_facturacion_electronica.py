"""Facturación electrónica vía Factiliza: mapeo tributario y ciclo de emisión.

Nunca toca la red — el cliente HTTP se reemplaza por un doble.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.core.database import Base
from src.modules.sales.application import comprobantes, ventas
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.models import Cliente, MedioPago
from src.modules.users.infrastructure.models import Persona
from src.shared.integrations import factiliza
from src.shared.integrations.factiliza import FactilizaError, RespuestaEmision
from tests.conftest import abrir_caja_directa
from tests.test_venta_slice import _crear_cadena_base, _crear_trabajador


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# --- Mapeo a los catálogos SUNAT --------------------------------------------
def _doc(exonerado: bool, precio="118.00", cantidad=1) -> factiliza.Documento:
    return factiliza.Documento(
        empresa_ruc="20450311520",
        tipo_doc=factiliza.TIPO_DOC_BOLETA,
        serie="B001",
        correlativo=1,
        fecha_emision=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        cliente=factiliza.Cliente(
            tipo_doc="0", num_doc="00000000", razon_social="CLIENTES VARIOS"
        ),
        items=[
            factiliza.Item(
                codigo="P001",
                descripcion="PIZZA FAMILIAR",
                cantidad=Decimal(cantidad),
                precio_unitario=Decimal(precio),
            )
        ],
        exonerado_igv=exonerado,
    )


def test_venta_gravada_desglosa_el_igv_hacia_atras() -> None:
    """El precio de carta ya incluye IGV: S/118 = S/100 de valor + S/18."""
    payload = factiliza.construir_payload(_doc(exonerado=False))
    assert payload["monto_Oper_Gravadas"] == 100.00
    assert payload["monto_Oper_Exoneradas"] == 0
    assert payload["monto_Igv"] == 18.00
    assert payload["monto_Imp_Venta"] == 118.00
    assert payload["detalle"][0]["tip_Afe_Igv"] == factiliza.mapper.AFECTACION_GRAVADO


def test_venta_en_amazonia_sale_exonerada_de_igv() -> None:
    """Ley 27037 (RN-IMP-001): Majambo vende en Tarapoto sin IGV — el total
    NO se desglosa, el precio de carta es el valor de venta."""
    payload = factiliza.construir_payload(_doc(exonerado=True))
    assert payload["monto_Oper_Gravadas"] == 0
    assert payload["monto_Oper_Exoneradas"] == 118.00
    assert payload["monto_Igv"] == 0
    assert payload["monto_Imp_Venta"] == 118.00
    assert payload["detalle"][0]["tip_Afe_Igv"] == factiliza.mapper.AFECTACION_EXONERADO


def test_totales_cuadran_con_varias_unidades() -> None:
    payload = factiliza.construir_payload(_doc(exonerado=False, cantidad=3))
    detalle = payload["detalle"][0]
    assert detalle["monto_Valor_Venta"] == 300.00
    assert payload["monto_Imp_Venta"] == 354.00
    assert payload["valor_Venta"] + payload["monto_Igv"] == payload["monto_Imp_Venta"]


@pytest.mark.parametrize(
    ("monto", "esperado"),
    [
        (Decimal("118.00"), "SON CIENTO DIECIOCHO CON 00/100 SOLES"),
        (Decimal("21.50"), "SON VEINTIUNO CON 50/100 SOLES"),
        (Decimal("900.05"), "SON NOVECIENTOS CON 05/100 SOLES"),
    ],
)
def test_monto_en_letras(monto: Decimal, esperado: str) -> None:
    assert factiliza.monto_en_letras(monto) == esperado


def test_leyenda_1000_va_en_el_payload() -> None:
    legend = factiliza.construir_payload(_doc(exonerado=True))["legend"][0]
    assert legend["legend_Code"] == factiliza.mapper.LEYENDA_MONTO_EN_LETRAS
    assert legend["legend_Value"].startswith("SON ")


# --- Regla boleta vs factura -------------------------------------------------
@pytest.mark.parametrize(
    ("tipo_cliente", "ruc", "esperado"),
    [
        (None, None, "boleta"),
        ("natural", None, "boleta"),
        ("juridico", None, "boleta"),
        ("juridico", "20552103816", "factura"),
    ],
)
def test_tipo_comprobante(tipo_cliente, ruc, esperado) -> None:
    assert rules.tipo_comprobante(tipo_cliente, ruc) == esperado


def test_descuento_se_reparte_en_el_precio_unitario() -> None:
    assert rules.precio_unitario_neto(
        Decimal(2), Decimal("50.00"), Decimal("10.00")
    ) == Decimal("45.00")


# --- Ciclo de emisión --------------------------------------------------------
class _ClienteFalso:
    def __init__(self, respuesta=None, error: Exception | None = None) -> None:
        self.respuesta = respuesta
        self.error = error
        self.payloads: list[dict] = []

    def enviar_comprobante(self, payload: dict) -> RespuestaEmision:
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.respuesta


def _aceptado() -> RespuestaEmision:
    return RespuestaEmision(
        aceptado=True,
        codigo_sunat="0",
        mensaje="Boleta numero B001-00000001 aceptada",
        hash="AeOqQVd8d5kfPS+CmeCMF+NNMpI=",
        crudo={"status": 200, "success": True},
    )


def _rechazado() -> RespuestaEmision:
    return RespuestaEmision(
        aceptado=False,
        codigo_sunat="2335",
        mensaje="El RUC del emisor no existe",
        hash=None,
        crudo={"status": 400, "success": False},
    )


def _venta_pagada(session, cliente=None):
    """`cliente` es una fábrica que recibe la empresa y devuelve un Cliente —
    la cadena base debe existir antes de poder crearlo."""
    empresa, sucursal, producto, punto_venta = _crear_cadena_base(session)
    usuario, _ = _crear_trabajador(session, empresa, "Ana", "Cajera", "10000001")
    cliente_id = cliente(session, empresa).id if cliente else None
    medio = MedioPago(
        empresa_id=empresa.id, nombre="Efectivo", direccion="cobro", tipo="efectivo"
    )
    session.add(medio)
    session.flush()
    # No se cobra sin turno de caja abierto (RN-MDP-002); acá se prueba la
    # facturación, no la caja, así que el turno se inserta directo.
    abrir_caja_directa(
        session, punto_venta_id=punto_venta.id, cajero_id=usuario.id
    )

    venta = ventas.crear_venta(
        session,
        sucursal_id=sucursal.id,
        punto_venta_id=punto_venta.id,
        canal="pdv",
        modalidad="mesa",
        usuario_id=usuario.id,
        idempotency_key=f"venta-{uuid.uuid4()}",
        items=[
            {
                "producto_comercial_id": producto.id,
                "cantidad": 1,
                "precio_unitario": Decimal("118.00"),
            }
        ],
        cliente_id=cliente_id,
    )
    _pago, venta, comprobante = ventas.registrar_pago(
        session,
        venta_id=venta.id,
        medio_pago_id=medio.id,
        monto=Decimal("118.00"),
        idempotency_key=f"pago-{uuid.uuid4()}",
    )
    return empresa, venta, comprobante


def test_cobrar_crea_el_comprobante_pendiente(session) -> None:
    """La caja no espera a SUNAT: el comprobante nace pendiente."""
    _empresa, venta, comprobante = _venta_pagada(session)
    assert venta.estado == "pagada"
    assert comprobante.estado_emision == "pendiente"
    assert comprobante.tipo == "boleta"
    assert (comprobante.serie, comprobante.correlativo) == ("B001", 1)


def test_cobrar_dos_veces_no_duplica_el_comprobante(session) -> None:
    _empresa, venta, comprobante = _venta_pagada(session)
    otra_vez = comprobantes.crear_comprobante_pendiente(session, venta)
    assert otra_vez.id == comprobante.id


def test_emision_aceptada_marca_la_venta_facturada(session) -> None:
    _empresa, venta, comprobante = _venta_pagada(session)
    cliente = _ClienteFalso(respuesta=_aceptado())

    resultado = comprobantes.emitir_comprobante(session, comprobante.id, cliente)

    assert resultado.estado_emision == "aceptado"
    assert resultado.hash_proveedor == "AeOqQVd8d5kfPS+CmeCMF+NNMpI="
    assert venta.estado == "facturada"
    # Majambo está en Amazonía: la boleta debe salir exonerada.
    assert cliente.payloads[0]["monto_Oper_Exoneradas"] == 118.00


def test_emision_rechazada_guarda_el_motivo_y_no_factura(session) -> None:
    """Un rechazo de SUNAT es un veredicto, no un error del sistema."""
    _empresa, venta, comprobante = _venta_pagada(session)

    resultado = comprobantes.emitir_comprobante(
        session, comprobante.id, _ClienteFalso(respuesta=_rechazado())
    )

    assert resultado.estado_emision == "rechazado"
    assert "RUC del emisor" in resultado.detalle_emision
    assert venta.estado == "pagada"


def test_emitir_dos_veces_no_reenvia_un_aceptado(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session)
    cliente = _ClienteFalso(respuesta=_aceptado())
    comprobantes.emitir_comprobante(session, comprobante.id, cliente)
    comprobantes.emitir_comprobante(session, comprobante.id, cliente)
    assert len(cliente.payloads) == 1


def test_fallo_de_transporte_propaga_para_que_la_cola_reintente(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session)
    cliente = _ClienteFalso(error=FactilizaError("Factiliza no responde"))

    with pytest.raises(FactilizaError):
        comprobantes.emitir_comprobante(session, comprobante.id, cliente)

    assert comprobante.intentos_emision == 1
    assert comprobante.estado_emision == "pendiente"


def test_intentos_agotados_frenan_el_reenvio(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session)
    comprobante.intentos_emision = comprobantes.MAX_INTENTOS_EMISION

    with pytest.raises(Exception, match="revisión manual"):
        comprobantes.emitir_comprobante(
            session, comprobante.id, _ClienteFalso(respuesta=_aceptado())
        )


def test_el_barrido_solo_recoge_lo_que_todavia_puede_emitirse(session) -> None:
    """La red de seguridad del beat: recoge lo que nunca llegó a la cola,
    pero no reintenta lo que SUNAT ya rechazó (datos malos: el reenvío da el
    mismo rechazo) ni lo que agotó sus intentos (daría `Conflicto` cada
    ciclo, para siempre)."""
    _empresa, _venta, comprobante = _venta_pagada(session)

    def _recogidos():
        session.flush()
        return comprobantes.pendientes_de_emitir(session)

    assert _recogidos() == [comprobante.id]  # nació pendiente, nunca se encoló

    comprobante.estado_emision = "error"  # fallo de transporte: reintentable
    assert _recogidos() == [comprobante.id]

    comprobante.intentos_emision = comprobantes.MAX_INTENTOS_EMISION
    assert _recogidos() == []

    comprobante.intentos_emision = 0
    comprobante.estado_emision = "rechazado"  # veredicto de SUNAT, no error
    assert _recogidos() == []

    comprobante.estado_emision = "aceptado"
    assert _recogidos() == []


def _cliente_juridico(session, empresa) -> Cliente:
    cliente = Cliente(
        grupo_id=empresa.grupo_id,
        tipo="juridico",
        razon_social="AGROLIGHT PERU S.A.C.",
        ruc="20552103816",
    )
    session.add(cliente)
    session.flush()
    return cliente


def _cliente_natural(session, empresa) -> Cliente:
    persona = Persona(
        nombres="Carlos",
        apellidos="Ramírez",
        tipo_documento="dni",
        numero_documento="45678912",
        domicilio="Jr. Lima 100",
    )
    session.add(persona)
    session.flush()
    cliente = Cliente(grupo_id=empresa.grupo_id, tipo="natural", persona_id=persona.id)
    session.add(cliente)
    session.flush()
    return cliente


def test_cliente_con_ruc_recibe_factura_con_su_serie(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session, cliente=_cliente_juridico)
    assert comprobante.tipo == "factura"
    assert comprobante.serie == "F001"

    doble = _ClienteFalso(respuesta=_aceptado())
    comprobantes.emitir_comprobante(session, comprobante.id, doble)
    payload = doble.payloads[0]
    assert payload["cliente_Tipo_Doc"] == rules.DOC_SUNAT_RUC
    assert payload["cliente_Num_Doc"] == "20552103816"
    assert payload["tipo_Doc"] == factiliza.TIPO_DOC_FACTURA


def test_cliente_natural_va_con_su_dni(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session, cliente=_cliente_natural)
    assert comprobante.tipo == "boleta"

    doble = _ClienteFalso(respuesta=_aceptado())
    comprobantes.emitir_comprobante(session, comprobante.id, doble)

    payload = doble.payloads[0]
    assert payload["cliente_Tipo_Doc"] == rules.DOC_SUNAT_DNI
    assert payload["cliente_Num_Doc"] == "45678912"
    assert payload["cliente_Razon_Social"] == "Carlos Ramírez"


def test_venta_anonima_usa_clientes_varios(session) -> None:
    _empresa, _venta, comprobante = _venta_pagada(session)
    doble = _ClienteFalso(respuesta=_aceptado())
    comprobantes.emitir_comprobante(session, comprobante.id, doble)
    assert doble.payloads[0]["cliente_Razon_Social"] == "CLIENTES VARIOS"


def test_sin_token_configurado_la_emision_queda_deshabilitada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El ERP opera sin facturación electrónica: los comprobantes se
    acumulan pendientes en vez de romper la caja."""
    from src.config import settings as modulo_settings

    monkeypatch.setattr(modulo_settings.settings, "factiliza_token", "")
    assert comprobantes.emision_habilitada() is False
    monkeypatch.setattr(modulo_settings.settings, "factiliza_token", "un-token")
    assert comprobantes.emision_habilitada() is True
