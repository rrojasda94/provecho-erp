"""Consulta RUC/DNI contra Factiliza (RENIEC/SUNAT vía el mismo proveedor,
RN-PTS-004 addendum 2026-08-02). Nunca toca la red: `httpx.get` se
reemplaza por un doble.
"""

from datetime import date

import httpx
import pytest
import redis

from src.config.settings import settings
from src.shared.integrations.factiliza import nombres_desde_dni, razon_social_desde_ruc
from src.shared.integrations.factiliza.client import (
    ConsultaEmpresa,
    ConsultaPersona,
    FactilizaClient,
    FactilizaError,
)


class _RespuestaFalsa:
    def __init__(self, status_code, texto, cuerpo=None):
        self.status_code = status_code
        self.text = texto
        self._cuerpo = cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin cuerpo")
        return self._cuerpo


def test_consultar_dni_encontrado(monkeypatch):
    cuerpo = {
        "success": True,
        "data": {
            "numero": "73632127",
            "nombres": "CARLOS RENATO",
            "apellido_paterno": "ROJAS",
            "apellido_materno": "DEL AGUILA",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_dni("73632127")
    assert r == ConsultaPersona(True, "73632127", "CARLOS RENATO", "ROJAS DEL AGUILA", cuerpo)


def test_consultar_ruc_encontrado(monkeypatch):
    cuerpo = {
        "success": True,
        "data": {
            "numero": "20610077782",
            "nombre_o_razon_social": "SERVICIOS RENTAURANT S.A.C",
            "estado": "BAJA DE OFICIO",
            "condicion": "HABIDO",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_ruc("20610077782")
    assert r == ConsultaEmpresa(
        True, "20610077782", "SERVICIOS RENTAURANT S.A.C", "BAJA DE OFICIO", "HABIDO", cuerpo
    )


def test_consultar_dni_no_encontrado_404_vacio_no_es_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(404, ""))
    r = FactilizaClient(token="t").consultar_dni("00000000")
    assert r.encontrado is False


def test_consultar_sin_token_configurado_lanza_factiliza_error():
    with pytest.raises(FactilizaError):
        FactilizaClient(token="").consultar_dni("73632127")


def test_nombres_desde_dni_hace_fallback_si_factiliza_falla(monkeypatch):
    def explota(self, dni):
        raise FactilizaError("caído")

    monkeypatch.setattr(FactilizaClient, "consultar_dni", explota)
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == ("Tecleado", "Apellido")


def test_nombres_desde_dni_hace_fallback_si_no_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_dni",
        lambda self, dni: ConsultaPersona(False, dni, "", "", {}),
    )
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == ("Tecleado", "Apellido")


def test_nombres_desde_dni_usa_factiliza_si_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_dni",
        lambda self, dni: ConsultaPersona(True, dni, "CARLOS RENATO", "ROJAS DEL AGUILA", {}),
    )
    assert nombres_desde_dni("73632127", "Tecleado", "Apellido") == (
        "CARLOS RENATO",
        "ROJAS DEL AGUILA",
    )


def test_razon_social_desde_ruc_hace_fallback_si_no_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_ruc",
        lambda self, ruc: ConsultaEmpresa(False, ruc, "", "", "", {}),
    )
    assert razon_social_desde_ruc("20610077782", "Tecleado SAC") == "Tecleado SAC"


def test_razon_social_desde_ruc_usa_factiliza_si_encuentra(monkeypatch):
    monkeypatch.setattr(
        FactilizaClient,
        "consultar_ruc",
        lambda self, ruc: ConsultaEmpresa(True, ruc, "SERVICIOS RENTAURANT S.A.C", "", "", {}),
    )
    assert razon_social_desde_ruc("20610077782", "Tecleado SAC") == "SERVICIOS RENTAURANT S.A.C"


def test_el_dni_trae_la_fecha_de_nacimiento_cuando_el_plan_la_incluye(monkeypatch):
    """RENIEC la devuelve según el plan contratado. Se acepta el formato que
    manda Factiliza (`dd/mm/aaaa`) y también ISO, porque son los dos que se
    han visto y ninguno está en el contrato escrito."""
    for crudo, esperada in (
        ("12/05/1994", date(1994, 5, 12)),
        ("1994-05-12", date(1994, 5, 12)),
        ("", None),
        ("no es una fecha", None),
    ):
        cuerpo = {
            "success": True,
            "data": {
                "numero": "73632127",
                "nombres": "CARLOS RENATO",
                "apellido_paterno": "ROJAS",
                "apellido_materno": "DEL AGUILA",
                "fecha_nacimiento": crudo,
            },
        }
        # `c=cuerpo`: la lambda se evalúa después del bucle, y sin fijarlo
        # las cuatro corridas leerían el último valor.
        monkeypatch.setattr(httpx, "get", lambda *a, c=cuerpo, **k: _RespuestaFalsa(200, "x", c))
        assert FactilizaClient(token="t").consultar_dni("73632127").fecha_nacimiento == esperada


def test_el_ruc_trae_el_domicilio_fiscal_partido(monkeypatch):
    """Partido y no como un solo texto: `provincia` es lo que decide si el
    flete es local o interprovincial, y volver a partirlo es adivinar."""
    cuerpo = {
        "success": True,
        "data": {
            "numero": "20610077782",
            "nombre_o_razon_social": "SERVICIOS RENTAURANT S.A.C",
            "estado": "ACTIVO",
            "condicion": "HABIDO",
            "direccion": "JR. ALEGRIA ARIAS DE MOREY NRO. 250",
            "distrito": "TARAPOTO",
            "provincia": "SAN MARTIN",
            "departamento": "SAN MARTIN",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_ruc("20610077782")
    assert r.direccion == "JR. ALEGRIA ARIAS DE MOREY NRO. 250"
    assert r.distrito == "TARAPOTO"
    assert r.provincia == "SAN MARTIN"
    assert r.departamento == "SAN MARTIN"


def test_un_ruc_sin_domicilio_no_rompe(monkeypatch):
    """El campo puede no venir: se devuelve vacío, no `None`, para que el
    formulario lo trate como "sin dato" sin comprobar el tipo."""
    cuerpo = {
        "success": True,
        "data": {"numero": "20610077782", "nombre_o_razon_social": "X S.A.C"},
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = FactilizaClient(token="t").consultar_ruc("20610077782")
    assert (r.direccion, r.distrito, r.provincia, r.departamento) == ("", "", "", "")


# --- El endpoint HTTP -------------------------------------------------------
@pytest.fixture()
def api(monkeypatch):
    """La consulta expuesta al frontend. Existía el cliente y existían los
    helpers que lo usan al crear, pero ninguna pantalla podía preguntar antes
    de tipear: `nombres_desde_dni` no se llamaba desde ningún caso de uso."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import src.core.models_registry  # noqa: F401
    from src.core.app import create_app
    from src.core.database import Base
    from src.modules.users.api.deps import get_db
    from src.modules.users.infrastructure.models import Rol, Usuario, UsuarioRol
    from src.modules.users.infrastructure.security import hash_pin
    from src.seeders.seed import seed

    # Sin token el cliente ni sale a la red y todo responde 502. Acá se
    # prueba el endpoint, no la configuración del despliegue.
    monkeypatch.setattr(settings, "factiliza_token", "token-de-prueba")

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as s:
        seed(s)
        # `caja1` no está de adorno: es el segundo usuario **con** el permiso,
        # y sale por la misma IP que `compras1` en el TestClient — que es
        # exactamente el caso que el límite por usuario tiene que distinguir.
        for username, rol in (
            ("compras1", "comprador"),
            ("caja1", "cajero"),
            ("cocina1", "cocinero"),
        ):
            u = Usuario(username=username, pin_hash=hash_pin("654321"), tipo="humano")
            s.add(u)
            s.flush()
            s.add(
                UsuarioRol(
                    usuario_id=u.id,
                    rol_id=s.scalar(select(Rol).where(Rol.nombre == rol)).id,
                )
            )
        s.commit()

    app = create_app()

    def _override():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c


def _tok(client, username, pin):
    r = client.post("/api/v1/auth/login", json={"username": username, "pin": pin})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_el_comprador_consulta_un_ruc_y_recibe_el_domicilio(api, monkeypatch):
    cuerpo = {
        "success": True,
        "data": {
            "numero": "20610077782",
            "nombre_o_razon_social": "SERVICIOS RENTAURANT S.A.C",
            "estado": "ACTIVO",
            "condicion": "HABIDO",
            "direccion": "JR. ALEGRIA ARIAS DE MOREY NRO. 250",
            "provincia": "SAN MARTIN",
            "departamento": "SAN MARTIN",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = api.get("/api/v1/consulta/ruc/20610077782", headers=_tok(api, "compras1", "654321"))
    assert r.status_code == 200, r.text
    assert r.json()["razon_social"] == "SERVICIOS RENTAURANT S.A.C"
    assert r.json()["provincia"] == "SAN MARTIN"


def test_la_consulta_no_devuelve_la_respuesta_cruda(api, monkeypatch):
    """El proveedor manda más datos personales de los que la pantalla
    necesita, y lo que no se manda no se filtra (Ley 29733)."""
    cuerpo = {
        "success": True,
        "data": {
            "numero": "73632127",
            "nombres": "CARLOS RENATO",
            "apellido_paterno": "ROJAS",
            "apellido_materno": "DEL AGUILA",
            "direccion": "un domicilio que nadie pidió",
        },
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(200, "x", cuerpo))
    r = api.get("/api/v1/consulta/dni/73632127", headers=_tok(api, "compras1", "654321"))
    assert r.status_code == 200, r.text
    assert set(r.json()) == {
        "encontrado",
        "numero_documento",
        "nombres",
        "apellidos",
        "fecha_nacimiento",
    }


def test_sin_el_permiso_no_se_consulta(api):
    """Es un permiso propio: cada consulta gasta cuota del proveedor y trae
    datos de alguien que todavía no es nadie en el sistema."""
    h = _tok(api, "cocina1", "654321")
    assert api.get("/api/v1/consulta/dni/73632127", headers=h).status_code == 403
    assert api.get("/api/v1/consulta/ruc/20610077782", headers=h).status_code == 403


def test_un_documento_mal_formado_no_llega_al_proveedor(api, monkeypatch):
    def _explota(*a, **k):
        raise AssertionError("no debería consultarse")

    monkeypatch.setattr(httpx, "get", _explota)
    h = _tok(api, "compras1", "654321")
    assert api.get("/api/v1/consulta/dni/123", headers=h).status_code == 422
    assert api.get("/api/v1/consulta/ruc/2061007778X", headers=h).status_code == 422


def test_el_proveedor_caido_es_502_y_no_500(api, monkeypatch):
    """El que falló es un tercero, y la diferencia importa: un 500 manda a
    revisar este servidor, que está bien."""

    def _cae(*a, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx, "get", _cae)
    r = api.get("/api/v1/consulta/ruc/20610077782", headers=_tok(api, "compras1", "654321"))
    assert r.status_code == 502, r.text


def test_documento_no_encontrado_no_es_error(api, monkeypatch):
    """El alta puede seguir tecleando el nombre: que RENIEC no lo tenga no
    es una falla del ERP."""
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _RespuestaFalsa(404, "", None))
    r = api.get("/api/v1/consulta/dni/73632127", headers=_tok(api, "compras1", "654321"))
    assert r.status_code == 200, r.text
    assert r.json()["encontrado"] is False


# --- Cuota (rate limit propio) ----------------------------------------------
# Lo que se cuida no es el abuso sino el **gasto**: cada consulta vale una
# llamada a un proveedor pago, así que un bucle mal escrito en una pantalla
# agota el plan del mes sin que nadie ataque nada.
DNI = "/api/v1/consulta/dni/73632127"
_CUERPO_DNI = {
    "success": True,
    "data": {
        "numero": "73632127",
        "nombres": "CARLOS RENATO",
        "apellido_paterno": "ROJAS",
        "apellido_materno": "DEL AGUILA",
    },
}


def _contar_llamadas(monkeypatch) -> list:
    """Reemplaza al proveedor por un doble que además anota cuántas veces lo
    llamaron: que el 429 corte **antes** de gastar cuota es el punto."""
    llamadas: list[int] = []

    def _get(*a, **k):
        llamadas.append(1)
        return _RespuestaFalsa(200, "x", _CUERPO_DNI)

    monkeypatch.setattr(httpx, "get", _get)
    return llamadas


def _cuota(monkeypatch, *, usuario: int, ip: int, ventana: int = 60) -> None:
    monkeypatch.setattr(settings, "consulta_documento_intentos_usuario", usuario)
    monkeypatch.setattr(settings, "consulta_documento_intentos_ip", ip)
    monkeypatch.setattr(settings, "consulta_documento_ventana_segundos", ventana)


def test_la_consulta_corta_al_pasarse_de_cuota(api, monkeypatch):
    """Y corta en la dependencia, sin llegar al proveedor: un 429 que igual
    gastó la llamada no habría servido de nada.

    La ventana es 45 y no 60 para que el `Retry-After` no pueda coincidir por
    casualidad con el del login, que es el otro límite del ERP.
    """
    _cuota(monkeypatch, usuario=2, ip=100, ventana=45)
    llamadas = _contar_llamadas(monkeypatch)
    h = _tok(api, "compras1", "654321")

    codigos = [api.get(DNI, headers=h).status_code for _ in range(3)]

    assert codigos == [200, 200, 429]
    assert len(llamadas) == 2
    assert api.get(DNI, headers=h).headers["Retry-After"] == "45"


def test_el_limite_por_usuario_no_deja_sin_consultar_al_de_al_lado(api, monkeypatch):
    """En un local todas las cajas salen por la misma IP —el TestClient
    también—, así que un límite solo por IP castigaría al equipo entero por
    uno solo. El segundo usuario tiene que poder seguir trabajando."""
    _cuota(monkeypatch, usuario=1, ip=100)
    _contar_llamadas(monkeypatch)
    comprador = _tok(api, "compras1", "654321")
    cajero = _tok(api, "caja1", "654321")

    assert api.get(DNI, headers=comprador).status_code == 200
    assert api.get(DNI, headers=comprador).status_code == 429
    assert api.get(DNI, headers=cajero).status_code == 200


def test_el_techo_de_la_ip_alcanza_a_todo_el_local(api, monkeypatch):
    """La contracara: el límite por usuario solo no frena a quien tiene dos
    cuentas a mano, así que la IP sigue siendo un techo del local entero."""
    _cuota(monkeypatch, usuario=100, ip=2)
    _contar_llamadas(monkeypatch)
    comprador = _tok(api, "compras1", "654321")
    cajero = _tok(api, "caja1", "654321")

    assert api.get(DNI, headers=comprador).status_code == 200
    assert api.get(DNI, headers=cajero).status_code == 200
    assert api.get(DNI, headers=cajero).status_code == 429


def test_con_redis_caido_la_consulta_no_se_bloquea(api, monkeypatch):
    """Fail-open deliberado (mismo criterio que el login): un Redis caído no
    puede dejar a la caja sin poder identificar a un cliente. Se acepta el
    costo —con Redis abajo la cuota del proveedor queda sin freno— porque la
    alternativa es no poder facturar."""
    from src.core import rate_limit as rl

    class _RedisCaido:
        def incr(self, clave):
            raise redis.RedisError("sin conexión")

        def expire(self, clave, segundos):
            raise redis.RedisError("sin conexión")

    monkeypatch.setattr(rl, "_client", _RedisCaido())
    monkeypatch.setattr(rl, "_reintentar_desde", 0.0)
    _cuota(monkeypatch, usuario=1, ip=1)
    _contar_llamadas(monkeypatch)
    h = _tok(api, "compras1", "654321")

    codigos = [api.get(DNI, headers=h).status_code for _ in range(4)]

    assert codigos == [200, 200, 200, 200]


# --- Dos tokens: emisión y consulta son productos distintos -----------------
# Factiliza cobra por separado la emisión de comprobantes y la consulta
# RUC/DNI, y entrega una credencial por cada una. Mandar el token de emisión
# al host de consulta devuelve 401 y el buscador de DNI del mostrador queda
# muerto sin que nadie sepa por qué — el síntoma es un 502 genérico.


def _capturar_authorization(monkeypatch, metodo="get"):
    """Reemplaza `httpx.get`/`httpx.post` y devuelve la lista donde van
    cayendo los Bearer que se enviaron."""
    enviados: list[str] = []

    def espia(*a, **k):
        enviados.append(k["headers"]["Authorization"])
        return _RespuestaFalsa(200, "x", {"success": True, "data": {}})

    monkeypatch.setattr(httpx, metodo, espia)
    return enviados


def test_la_consulta_usa_su_propio_token(monkeypatch):
    monkeypatch.setattr(settings, "factiliza_token", "el-de-emision")
    monkeypatch.setattr(settings, "factiliza_consulta_documento_token", "el-de-consulta")
    enviados = _capturar_authorization(monkeypatch)
    FactilizaClient().consultar_dni("73632127")
    assert enviados == ["Bearer el-de-consulta"]


def test_la_emision_nunca_usa_el_token_de_consulta(monkeypatch):
    """El cruce inverso: un comprobante enviado con la credencial de consulta
    lo rechaza SUNAT, y eso sí se ve en la caja."""
    monkeypatch.setattr(settings, "factiliza_token", "el-de-emision")
    monkeypatch.setattr(settings, "factiliza_consulta_documento_token", "el-de-consulta")
    enviados = _capturar_authorization(monkeypatch, metodo="post")
    FactilizaClient().enviar_comprobante({})
    assert enviados == ["Bearer el-de-emision"]


def test_sin_token_de_consulta_se_reusa_el_de_emision(monkeypatch):
    """Compatibilidad: quien tenga un solo token —plan que cubre ambos
    productos— no configura nada nuevo y sigue andando."""
    monkeypatch.setattr(settings, "factiliza_token", "el-unico")
    monkeypatch.setattr(settings, "factiliza_consulta_documento_token", "")
    enviados = _capturar_authorization(monkeypatch)
    FactilizaClient().consultar_ruc("20610077782")
    assert enviados == ["Bearer el-unico"]


def test_sin_ninguno_de_los_dos_la_consulta_falla_antes_de_salir_a_la_red(monkeypatch):
    monkeypatch.setattr(settings, "factiliza_token", "")
    monkeypatch.setattr(settings, "factiliza_consulta_documento_token", "")
    with pytest.raises(FactilizaError, match="FACTILIZA_CONSULTA_DOCUMENTO_TOKEN"):
        FactilizaClient().consultar_dni("73632127")
