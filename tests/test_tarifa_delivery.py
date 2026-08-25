"""Cuánto se cobra por llevar un pedido y cuándo no se lleva (ADR-054).

Lo que se prueba acá es plata: un error en `costo_de` no rompe nada, cobra
mal. Y lo que más importa no es el cálculo sino los caminos de escape —
Google caído, sucursal sin anclar, zona vetada— porque son los que deciden si
el restaurante puede seguir tomando pedidos.

Ninguna prueba sale a internet: el adaptador se reemplaza con `monkeypatch`.
"""

from decimal import Decimal

import pytest

from src.config.settings import settings
from src.modules.sales.application import tarifa_delivery
from src.modules.sales.application.tarifa_delivery import (
    MOTIVO_FUERA_DE_RADIO,
    MOTIVO_ZONA_RESTRINGIDA,
    Cotizacion,
    cotizar,
    linea_recta_km,
)
from src.shared.integrations.google import Coordenada, RutasError

# Dos puntos reales de Tarapoto: la plaza y el aeropuerto, ~2,5 km de manejo.
PLAZA = Coordenada(Decimal("-6.488430"), Decimal("-76.365280"))
AEROPUERTO = Coordenada(Decimal("-6.508700"), Decimal("-76.373300"))


@pytest.fixture(autouse=True)
def tarifa(monkeypatch):
    """Enciende la función: de fábrica está en cero y no cobra nada."""
    monkeypatch.setattr(settings, "delivery_tarifa_base", Decimal("3"))
    monkeypatch.setattr(settings, "delivery_precio_por_km", Decimal("1.50"))
    monkeypatch.setattr(settings, "delivery_distancia_maxima_km", Decimal("8"))
    monkeypatch.setattr(settings, "delivery_distritos_restringidos", ["Belén"])
    # La caché es por proceso y sobreviviría de un test al otro, sirviendo la
    # distancia que dejó el anterior.
    tarifa_delivery._distancia_cacheada.cache_clear()


def _google_dice(monkeypatch, km: str | None):
    monkeypatch.setattr(
        tarifa_delivery, "distancia_km", lambda o, d: None if km is None else Decimal(km)
    )


def _google_caido(monkeypatch):
    def _explotar(origen, destino):
        raise RutasError("Google Routes no responde")

    monkeypatch.setattr(tarifa_delivery, "distancia_km", _explotar)


# --- El cálculo -------------------------------------------------------------
def test_cobra_base_mas_kilometro(monkeypatch):
    _google_dice(monkeypatch, "4.00")
    c = cotizar(PLAZA, AEROPUERTO)
    assert c.distancia_km == Decimal("4.00")
    # 3 de base + 4 km × 1,50.
    assert c.costo == Decimal("9.00")
    assert c.aproximada is False
    assert c.derivar_a_externo is False


def test_la_configuracion_en_cero_no_cobra_nada(monkeypatch):
    """El estado de fábrica: la función existe pero está apagada, y el
    delivery se sigue cobrando como antes de este cambio."""
    monkeypatch.setattr(settings, "delivery_tarifa_base", Decimal("0"))
    monkeypatch.setattr(settings, "delivery_precio_por_km", Decimal("0"))
    monkeypatch.setattr(settings, "delivery_distancia_maxima_km", Decimal("0"))
    _google_dice(monkeypatch, "40.00")
    c = cotizar(PLAZA, AEROPUERTO)
    assert c.costo == Decimal("0.00")
    # Sin radio configurado no se deriva nada, por lejos que quede.
    assert c.derivar_a_externo is False


# --- Cuándo se deriva -------------------------------------------------------
def test_mas_lejos_del_radio_se_sugiere_la_plataforma_externa(monkeypatch):
    _google_dice(monkeypatch, "13.40")
    c = cotizar(PLAZA, AEROPUERTO)
    assert c.derivar_a_externo is True
    assert c.motivo == MOTIVO_FUERA_DE_RADIO


def test_zona_restringida_no_gasta_una_llamada(monkeypatch):
    """La zona vetada no depende de la distancia: preguntarle a Google sería
    pagar por una respuesta que ya se sabe."""
    llamadas = []
    monkeypatch.setattr(
        tarifa_delivery,
        "distancia_km",
        lambda o, d: llamadas.append(1) or Decimal("1"),
    )
    c = cotizar(PLAZA, AEROPUERTO, distrito_destino="Belen")
    assert c.derivar_a_externo is True
    assert c.motivo == MOTIVO_ZONA_RESTRINGIDA
    assert llamadas == [], "se llamó a Google por una zona ya vetada"


def test_el_distrito_se_compara_sin_tildes_ni_mayusculas(monkeypatch):
    _google_dice(monkeypatch, "1.00")
    for escrito in ("Belén", "BELEN", " belen "):
        assert cotizar(PLAZA, AEROPUERTO, escrito).motivo == MOTIVO_ZONA_RESTRINGIDA


def test_un_destino_sin_ruta_se_deriva(monkeypatch):
    """Google contestó, pero no hay forma de manejar hasta ahí."""
    _google_dice(monkeypatch, None)
    c = cotizar(PLAZA, AEROPUERTO)
    assert c.distancia_km is None
    assert c.derivar_a_externo is True


# --- Lo que no se puede romper ----------------------------------------------
def test_google_caido_no_impide_tomar_el_pedido(monkeypatch):
    """Cobrar de menos por un kilómetro es preferible a no poder vender.
    Es además lo único que funciona en el hub offline de una sucursal."""
    _google_caido(monkeypatch)
    c = cotizar(PLAZA, AEROPUERTO)
    assert c.aproximada is True
    assert c.distancia_km is not None and c.distancia_km > 0
    assert c.costo > Decimal("3")


def test_una_sucursal_sin_anclar_cobra_la_base(monkeypatch):
    """El estado de todas las sucursales el día que esto se despliega."""
    _google_dice(monkeypatch, "4.00")
    c = cotizar(None, AEROPUERTO)
    assert c == Cotizacion(None, Decimal("3"), False, False)


def test_una_direccion_escrita_a_mano_cobra_la_base(monkeypatch):
    _google_dice(monkeypatch, "4.00")
    assert cotizar(PLAZA, None).costo == Decimal("3")


# --- El plan B --------------------------------------------------------------
def test_la_linea_recta_se_parece_a_la_distancia_real():
    """No tiene que ser exacta —para eso está Google— pero sí del mismo orden:
    una estimación que diga 200 m donde hay 2,5 km cobraría cualquier cosa."""
    aprox = linea_recta_km(PLAZA, AEROPUERTO)
    assert Decimal("2") < aprox < Decimal("5")


def test_un_fallo_de_google_no_queda_cacheado(monkeypatch):
    """Si la estimación aproximada se cacheara, una caída de dos minutos
    dejaría cobrando de menos hasta el próximo reinicio."""
    _google_caido(monkeypatch)
    assert cotizar(PLAZA, AEROPUERTO).aproximada is True
    _google_dice(monkeypatch, "4.00")
    segunda = cotizar(PLAZA, AEROPUERTO)
    assert segunda.aproximada is False
    assert segunda.distancia_km == Decimal("4.00")


def test_la_segunda_cotizacion_no_vuelve_a_preguntar(monkeypatch):
    """La misma puerta se cotiza dos veces por pedido: la que ve el cajero y
    la que congela la orden. Google se paga por llamada."""
    llamadas = []

    def _contar(origen, destino):
        llamadas.append(1)
        return Decimal("4.00")

    monkeypatch.setattr(tarifa_delivery, "distancia_km", _contar)
    cotizar(PLAZA, AEROPUERTO)
    cotizar(PLAZA, AEROPUERTO)
    assert len(llamadas) == 1


# --- Quién fija la tarifa (ADR-066) -----------------------------------------
@pytest.fixture()
def empresa():
    """Una empresa real con su admin: `parametro_empresa` tiene FK a las dos.

    Se siembra con el seeder en vez de armar las filas a mano porque lo que
    se prueba es la lectura del parámetro, no el alta de una empresa.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import src.core.models_registry  # noqa: F401
    from src.core.database import Base
    from src.modules.users.infrastructure.models import Empresa, Usuario
    from src.seeders.seed import seed

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        seed(s)
        s.commit()
        yield s, s.scalar(select(Empresa)).id, s.scalar(
            select(Usuario).where(Usuario.username == "admin")
        ).id


def _aprobar(session, empresa_id, admin_id, codigo: str, valor: dict) -> None:
    from src.shared.models import ParametroEmpresa

    session.add(
        ParametroEmpresa(
            empresa_id=empresa_id,
            modulo="sales",
            codigo=codigo,
            valor=valor,
            estado="vigente",
            propuesto_por_id=admin_id,
        )
    )
    session.flush()


def test_sin_parametro_aprobado_manda_la_semilla_del_env(empresa):
    """El día del despliegue no hay ningún parámetro aprobado y el ERP tiene
    que seguir cobrando exactamente lo de antes."""
    session, empresa_id, _ = empresa
    t = tarifa_delivery.tarifa_de(session, empresa_id)
    assert t.base == Decimal("3")
    assert t.por_km == Decimal("1.50")
    assert t.distritos_restringidos == ("Belén",)


def test_lo_que_aprueba_gerencia_manda_sobre_el_env(empresa, monkeypatch):
    session, empresa_id, admin_id = empresa
    _aprobar(session, empresa_id, admin_id, "delivery_precio_por_km",
             {"monto": "2.50", "divisa": "PEN"})
    _aprobar(session, empresa_id, admin_id, "delivery_tarifa_base",
             {"monto": "4.00", "divisa": "PEN"})
    _aprobar(session, empresa_id, admin_id, "delivery_distritos_restringidos",
             {"distritos": ["Morales"]})

    _google_dice(monkeypatch, "4.00")
    c = cotizar(PLAZA, AEROPUERTO, tarifa=tarifa_delivery.tarifa_de(session, empresa_id))
    # 4 de base + 4 km × 2,50 — nada de lo que dice el `.env`.
    assert c.costo == Decimal("14.00")
    # Y el distrito vetado también salió del parámetro, no del `.env`.
    aprobada = tarifa_delivery.tarifa_de(session, empresa_id)
    assert cotizar(PLAZA, AEROPUERTO, "Morales", aprobada).motivo == (
        MOTIVO_ZONA_RESTRINGIDA
    )
    assert cotizar(PLAZA, AEROPUERTO, "Belén", aprobada).motivo is None


def test_una_propuesta_sin_aprobar_no_cobra_nada(empresa):
    """Todo el mecanismo de ADR-014: el valor no surte efecto hasta que
    Gerencia lo aprueba (RN-GER-009)."""
    from src.shared.models import ParametroEmpresa

    session, empresa_id, admin_id = empresa
    session.add(
        ParametroEmpresa(
            empresa_id=empresa_id,
            modulo="sales",
            codigo="delivery_precio_por_km",
            valor={"monto": "99.00", "divisa": "PEN"},
            estado="propuesto",
            propuesto_por_id=admin_id,
        )
    )
    session.flush()
    assert tarifa_delivery.tarifa_de(session, empresa_id).por_km == Decimal("1.50")


def test_un_parametro_mal_formado_cobra_la_semilla(empresa):
    """El valor es un JSON que pasó por un formulario. Cobrar la semilla es
    peor que cobrar lo aprobado, pero infinitamente mejor que un 500 en caja."""
    session, empresa_id, admin_id = empresa
    _aprobar(session, empresa_id, admin_id, "delivery_precio_por_km",
             {"monto": "no es un número", "divisa": "PEN"})
    assert tarifa_delivery.tarifa_de(session, empresa_id).por_km == Decimal("1.50")


def test_una_sucursal_inexistente_no_rompe_la_cotizacion(empresa):
    session, _, _ = empresa
    import uuid as _uuid

    origen, empresa_id = tarifa_delivery.contexto_de_sucursal(session, _uuid.uuid4())
    assert origen is None and empresa_id is None
    # Y sin empresa se usa la semilla, que es el comportamiento de siempre.
    assert tarifa_delivery.tarifa_de(session, None) == tarifa_delivery.tarifa_semilla()
