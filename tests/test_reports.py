"""Emisión y distribución de reportes (ADR-033).

**Ojo con el vecino**: `tests/test_reportes.py` (en español) prueba el motor
de *consulta* de `core/reportes`. Este archivo prueba el módulo de *emisión y
distribución*. Son cosas distintas y por eso están separadas.

Lo que importa acá: que el hecho llegue a quien tiene que llegar, que quien
no debe verlo no lo vea aunque se lo hayan entregado, y que cambiar la regla
mañana no reescriba a quién le llegó ayer.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.core.models_registry  # noqa: F401
from src.core.app import create_app
from src.core.database import Base
from src.modules.reports.application import destinatarios as resolucion
from src.modules.reports.application import emision as emision_uc
from src.modules.reports.application import reglas as reglas_uc
from src.modules.reports.domain import catalogo, rules
from src.modules.reports.infrastructure.models import (
    Area,
    AreaMiembro,
    EntregaReporte,
    ReglaDestinatario,
    ReglaDistribucion,
    ReporteEmitido,
)
from src.modules.sales.infrastructure.models import PuntoVenta
from src.modules.users.api.deps import get_db
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Grupo,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared.models import AuditLog
from tests.conftest import abrir_caja_directa


# =============================================================================
# Dominio puro: el catálogo. Sin BD, sin HTTP.
# =============================================================================
def test_los_codigos_del_catalogo_son_unicos():
    """`codigo` es el nombre del evento y la clave de `regla_distribucion`.
    Dos emisiones con el mismo código harían que una regla apunte a las dos y
    que el listener se registre dos veces sobre el mismo hecho."""
    codigos = [e.codigo for e in catalogo.CATALOGO]
    assert len(codigos) == len(set(codigos))


@pytest.mark.parametrize("emision", catalogo.CATALOGO, ids=lambda e: e.codigo)
def test_las_plantillas_solo_usan_campos_declarados(emision):
    """Una plantilla que interpola un campo fuera de `campos` mostraría un
    dato que la whitelist decidió no guardar — o un `—` para siempre."""
    assert catalogo.placeholders_invalidos(emision) == set()


@pytest.mark.parametrize("emision", catalogo.CATALOGO, ids=lambda e: e.codigo)
def test_toda_emision_declara_permiso_ambito_y_nivel_validos(emision):
    assert emision.nivel in catalogo.NIVELES
    assert emision.ambito in catalogo.AMBITOS
    # El permiso es el del módulo dueño: `<modulo>.<verbo>`. Nunca uno propio
    # de reports —habría dos matrices de permisos que mantener— salvo cuando
    # el hecho **es** de reports, que es el caso de la cadena de escalamiento.
    assert "." in emision.permiso
    if not emision.codigo.startswith("reports."):
        assert not emision.permiso.startswith("reports.")
    assert emision.clave_referencia in emision.campos


# Emisiones que no tienen actor y no pueden tenerlo. Cada entrada acá es una
# decisión, no un olvido: si mañana alguien agrega una emisión y se olvida de
# `clave_actor`, el test de abajo falla en CI en vez de perder el dato en
# silencio.
SIN_ACTOR = {
    # Lo detecta un barrido de Celery. El hecho es «el pedido siguió en
    # cocina pasado el umbral», no «alguien tomó el pedido»: atribuírselo al
    # mozo sería acusarlo de algo que no hizo (RN-REP-009).
    "sales.pedido_demorado",
}


@pytest.mark.parametrize("emision", catalogo.CATALOGO, ids=lambda e: e.codigo)
def test_toda_emision_declara_actor_o_esta_declarada_sin_el(emision):
    assert bool(emision.clave_actor) != (emision.codigo in SIN_ACTOR)


@pytest.mark.parametrize("emision", catalogo.CATALOGO, ids=lambda e: e.codigo)
def test_el_campo_del_ambito_esta_declarado(emision):
    """Sin él, `_ubicar` no puede sacar la empresa del hecho y el reporte
    quedaría sin tenant."""
    assert emision.clave_ambito in emision.campos


@pytest.mark.parametrize("emision", catalogo.CATALOGO, ids=lambda e: e.codigo)
def test_las_areas_sugeridas_existen_en_las_areas_base(emision):
    """El seeder crea las reglas apuntando a estas áreas. Una sugerencia con
    un código que no se siembra deja la emisión sin destinatarios y en
    silencio."""
    base = {codigo for codigo, _ in catalogo.AREAS_BASE}
    assert set(emision.areas_sugeridas) <= base
    assert set(emision.dinamicos_sugeridos) <= set(catalogo.DINAMICOS)


def test_proyectar_descarta_lo_no_declarado():
    """RN-REP-003: solo lo declarado se persiste. Un payload que trae de más
    no se filtra al cliente por olvido de nadie."""
    emision = catalogo.obtener("inventory.ajuste_fuera_margen")
    datos = catalogo.proyectar(
        emision,
        {"ajuste_id": "a", "almacen_id": "b", "costo_interno": "SECRETO"},
    )
    assert "costo_interno" not in datos
    assert datos["ajuste_id"] == "a" and datos["almacen_id"] == "b"


def test_proyectar_conserva_el_campo_ausente_como_none():
    """Un campo que faltó es un dato que faltó, no un campo que no existe."""
    emision = catalogo.obtener("inventory.ajuste_fuera_margen")
    datos = catalogo.proyectar(emision, {"ajuste_id": "a"})
    assert set(datos) == set(emision.campos)
    assert datos["ajuste_id"] == "a"
    assert datos["almacen_id"] is None


def test_render_no_revienta_por_un_campo_faltante():
    """Una emisión no puede perderse porque el emisor omitió un opcional."""
    assert catalogo.render("hola {falta}", {}) == "hola —"


def test_visibles_recorta_por_permiso_y_el_comodin_ve_todo():
    solo_ventas = catalogo.visibles({"sales.leer"})
    assert solo_ventas and all(e.permiso == "sales.leer" for e in solo_ventas)
    assert len(catalogo.visibles({"*"})) == len(catalogo.CATALOGO)
    assert catalogo.visibles(set()) == []


# --- Elección de regla (RN-REP-008) ------------------------------------------
class _ReglaFalsa:
    def __init__(self, sucursal_id):
        self.sucursal_id = sucursal_id


def test_la_regla_de_la_sucursal_le_gana_a_la_general():
    """Si aplicaran las dos, quien esté en ambas recibiría dos veces."""
    sucursal = uuid.uuid4()
    general, especifica = _ReglaFalsa(None), _ReglaFalsa(sucursal)
    assert rules.elegir_regla([general, especifica], sucursal) is especifica
    assert rules.elegir_regla([especifica, general], sucursal) is especifica


def test_sin_regla_especifica_cubre_la_general():
    general = _ReglaFalsa(None)
    assert rules.elegir_regla([general], uuid.uuid4()) is general


def test_sin_ninguna_regla_no_hay_eleccion():
    assert rules.elegir_regla([], uuid.uuid4()) is None
    assert rules.elegir_regla([_ReglaFalsa(uuid.uuid4())], uuid.uuid4()) is None


# =============================================================================
# Con base: resolución de destinatarios y emisión.
# =============================================================================
@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        grupo = Grupo(nombre="Grupo Majambo")
        s.add(grupo)
        s.flush()
        empresa = Empresa(
            grupo_id=grupo.id, razon_social="Majambo EIRL", ruc="20100000001",
            domicilio_fiscal="Jr. X 1", tipo="operativa",
        )
        marca = Marca(grupo_id=grupo.id, nombre="Charlie's", tipo="restaurante")
        s.add_all([empresa, marca])
        s.flush()
        sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="CH1",
            direccion="Jr. X 123", tenencia="alquilada",
        )
        otra_sucursal = Sucursal(
            marca_id=marca.id, empresa_id=empresa.id, nombre="CH2",
            direccion="Jr. Y 456", tenencia="alquilada",
        )
        s.add_all([sucursal, otra_sucursal])
        s.flush()
        pv = PuntoVenta(
            sucursal_id=sucursal.id, canal="trabajador", serie_boleta="B001",
            serie_factura="F001", politica_pago="adelantado",
        )
        rol_sup = Rol(nombre="supervisor")
        rol_alm = Rol(nombre="almacenero")
        alm_sucursal = Almacen(
            empresa_id=empresa.id, sucursal_id=sucursal.id,
            nombre="Almacén CH1", tipo="sucursal",
        )
        alm_central = Almacen(empresa_id=empresa.id, nombre="Central", tipo="central")
        s.add_all([pv, rol_sup, rol_alm, alm_sucursal, alm_central])
        s.flush()

        usuarios = {}
        for nombre in ("cajero", "encargado", "supervisor1", "almacenero1"):
            u = Usuario(username=nombre, pin_hash=hash_pin("654321"), tipo="humano")
            s.add(u)
            s.flush()
            s.add(UsuarioSucursal(usuario_id=u.id, sucursal_id=sucursal.id))
            usuarios[nombre] = u
        s.add(UsuarioRol(usuario_id=usuarios["supervisor1"].id, rol_id=rol_sup.id))
        s.add(UsuarioRol(usuario_id=usuarios["almacenero1"].id, rol_id=rol_alm.id))

        area_almacen = Area(empresa_id=empresa.id, codigo="almacen", nombre="Almacén")
        area_gerencia = Area(empresa_id=empresa.id, codigo="gerencia", nombre="Gerencia")
        s.add_all([area_almacen, area_gerencia])
        s.flush()
        s.add(AreaMiembro(area_id=area_almacen.id, rol_id=rol_alm.id))
        s.add(AreaMiembro(area_id=area_gerencia.id, rol_id=rol_sup.id))
        s.commit()

        yield s, {
            "empresa": empresa, "sucursal": sucursal, "otra_sucursal": otra_sucursal,
            "pv": pv, "alm_sucursal": alm_sucursal, "alm_central": alm_central,
            "rol_sup": rol_sup, "rol_alm": rol_alm,
            "area_almacen": area_almacen, "area_gerencia": area_gerencia,
            **usuarios,
        }


def _abrir_caja(s, ids, *, con_encargado=True):
    """Turno de caja abierto.

    Por defecto escribe `relevo_encargado_id`, que es lo que dejaban las
    aperturas **anteriores a ADR-048**: desde entonces el cajero abre solo y
    la columna queda en NULL. Los resolutores tienen que seguir leyendo bien
    las filas viejas —existen en cualquier base que ya operó— y caer en el
    respaldo por rol con las nuevas.
    """
    apertura = abrir_caja_directa(
        s,
        punto_venta_id=ids["pv"].id,
        cajero_id=ids["cajero"].id,
        encargado_id=ids["encargado"].id if con_encargado else None,
        monto="100.00",
    )
    s.flush()
    return apertura


def _regla(s, ids, codigo, destinatarios, *, sucursal_id=None, nivel="aviso"):
    regla = ReglaDistribucion(
        empresa_id=ids["empresa"].id,
        codigo_emision=codigo,
        sucursal_id=sucursal_id,
        nivel=nivel,
    )
    s.add(regla)
    s.flush()
    for d in destinatarios:
        s.add(ReglaDestinatario(regla_id=regla.id, **d))
    s.flush()
    return regla


# --- Resolutores dinámicos (migrados desde `users`) ---------------------------
def test_el_aviso_va_al_encargado_de_turno(env):
    s, ids = env
    _abrir_caja(s, ids)
    assert resolucion.de_sucursal(s, ids["sucursal"].id) == [ids["encargado"].id]


def test_sin_caja_abierta_el_aviso_cae_en_los_supervisores(env):
    """Local cerrado o caja sin registrar: avisarle a alguien de más es mejor
    que perder el aviso."""
    s, ids = env
    assert resolucion.de_sucursal(s, ids["sucursal"].id) == [ids["supervisor1"].id]


def test_con_apertura_nueva_el_aviso_tambien_cae_en_los_supervisores(env):
    """Desde ADR-048 la caja abierta no nombra a ningún encargado, así que el
    respaldo por rol dejó de ser la excepción y pasó a ser el camino normal.

    Se congela acá porque es el efecto colateral de sacarle la firma a la
    apertura: si mañana alguien vuelve a necesitar un encargado de turno de
    verdad, va a hacer falta una fuente propia y no la caja.
    """
    s, ids = env
    _abrir_caja(s, ids, con_encargado=False)
    assert resolucion.de_sucursal(s, ids["sucursal"].id) == [ids["supervisor1"].id]


def test_una_sucursal_sin_nadie_asignado_no_revienta(env):
    s, ids = env
    assert resolucion.de_sucursal(s, ids["otra_sucursal"].id) == []


def test_el_almacen_central_no_tiene_encargado_de_turno_y_avisa_por_rol(env):
    """El central no cuelga de ninguna sucursal, así que no hay caja abierta
    que diga quién está a cargo. Se resuelve por rol dentro de la empresa."""
    s, ids = env
    assert set(resolucion.de_almacen(s, ids["alm_central"].id)) == {
        ids["almacenero1"].id,
        ids["supervisor1"].id,
    }


def test_el_almacen_de_sucursal_suma_al_encargado_de_turno(env):
    s, ids = env
    _abrir_caja(s, ids)
    s.flush()
    assert set(resolucion.de_almacen(s, ids["alm_sucursal"].id)) == {
        ids["almacenero1"].id,
        ids["supervisor1"].id,
        ids["encargado"].id,
    }


# --- Resolución de una regla completa ----------------------------------------
def test_un_area_resuelve_a_las_personas_de_sus_roles(env):
    s, ids = env
    entregas = resolucion.resolver(
        s,
        [ReglaDestinatario(tipo="area", area_id=ids["area_almacen"].id)],
        empresa_id=ids["empresa"].id,
        sucursal_id=ids["sucursal"].id,
        almacen_id=None,
    )
    assert [u for u, _ in entregas] == [ids["almacenero1"].id]
    assert entregas[0][1] == f"area:{ids['area_almacen'].id}"


def test_una_persona_en_dos_destinos_recibe_una_sola_vez(env):
    """Quien está en el área Almacén y además tiene el rol suelto no puede
    recibir dos entregas del mismo hecho."""
    s, ids = env
    entregas = resolucion.resolver(
        s,
        [
            ReglaDestinatario(tipo="area", area_id=ids["area_almacen"].id),
            ReglaDestinatario(tipo="rol", rol_id=ids["rol_alm"].id),
        ],
        empresa_id=ids["empresa"].id,
        sucursal_id=ids["sucursal"].id,
        almacen_id=None,
    )
    assert len(entregas) == 1
    # Gana el primer motivo declarado en la regla.
    assert entregas[0][1].startswith("area:")


def test_un_miembro_acotado_a_otra_sucursal_no_entra(env):
    """«El almacenero de Tarapoto es del área Almacén, pero solo para lo que
    pasa en Tarapoto»."""
    s, ids = env
    area = Area(empresa_id=ids["empresa"].id, codigo="caja", nombre="Caja")
    s.add(area)
    s.flush()
    s.add(
        AreaMiembro(
            area_id=area.id,
            rol_id=ids["rol_sup"].id,
            sucursal_id=ids["otra_sucursal"].id,
        )
    )
    s.flush()
    entregas = resolucion.resolver(
        s,
        [ReglaDestinatario(tipo="area", area_id=area.id)],
        empresa_id=ids["empresa"].id,
        sucursal_id=ids["sucursal"].id,
        almacen_id=None,
    )
    assert entregas == []


def test_un_dinamico_que_no_aplica_al_ambito_resuelve_a_nadie(env):
    """Pedir el encargado de turno de un hecho sin sucursal no puede
    resolver a *todos*: resuelve a nadie."""
    s, ids = env
    entregas = resolucion.resolver(
        s,
        [ReglaDestinatario(tipo="dinamico", dinamico="encargado_de_turno")],
        empresa_id=ids["empresa"].id,
        sucursal_id=None,
        almacen_id=None,
    )
    assert entregas == []


# --- Emisión ------------------------------------------------------------------
def test_emitir_guarda_la_foto_y_una_entrega_por_destinatario(env):
    s, ids = env
    _regla(
        s, ids, "inventory.ajuste_fuera_margen",
        [{"tipo": "area", "area_id": ids["area_almacen"].id}],
    )
    ajuste_id = uuid.uuid4()

    reporte, destinatarios = emision_uc.emitir(
        s,
        "inventory.ajuste_fuera_margen",
        {"ajuste_id": str(ajuste_id), "almacen_id": str(ids["alm_central"].id)},
    )
    s.flush()

    assert destinatarios == [ids["almacenero1"].id]
    assert reporte.empresa_id == ids["empresa"].id
    assert reporte.referencia_id == ajuste_id
    assert reporte.referencia_tipo == "ajuste"
    assert reporte.datos["ajuste_id"] == str(ajuste_id)
    assert reporte.datos["almacen_id"] == str(ids["alm_central"].id)
    (entrega,) = s.scalars(select(EntregaReporte)).all()
    assert entrega.motivo == f"area:{ids['area_almacen'].id}"


def test_un_codigo_fuera_del_catalogo_no_emite_nada(env):
    """Un evento sin emisión declarada no es un error: es un hecho que nadie
    pidió reportar."""
    s, _ = env
    assert emision_uc.emitir(s, "sales.venta_pagada", {}) is None


def test_sin_regla_el_reporte_se_guarda_igual_sin_entregas(env):
    """RN-REP-005. Antes era un `log.warning` que nadie leía; ahora es una
    fila y un hueco visible en la matriz."""
    s, ids = env
    reporte, destinatarios = emision_uc.emitir(
        s,
        "inventory.ajuste_fuera_margen",
        {"ajuste_id": str(uuid.uuid4()), "almacen_id": str(ids["alm_central"].id)},
    )
    s.flush()
    assert destinatarios == []
    assert reporte.regla_id is None
    assert s.scalars(select(EntregaReporte)).all() == []


def test_el_ambito_almacen_deduce_empresa_y_sucursal(env):
    s, ids = env
    reporte, _ = emision_uc.emitir(
        s,
        "inventory.stock_bajo_minimo",
        {
            "almacen_id": str(ids["alm_sucursal"].id),
            "sku_id": str(uuid.uuid4()),
            "cantidad": "4.0000",
            "stock_minimo": "5.0000",
        },
    )
    s.flush()
    assert reporte.empresa_id == ids["empresa"].id
    assert reporte.sucursal_id == ids["sucursal"].id
    # `_ubicar` ya lo resolvía para elegir destinatarios y lo descartaba: sin
    # él, el reporte no dice en qué almacén hay que reponer.
    assert reporte.almacen_id == ids["alm_sucursal"].id
    # El título sale de la plantilla, con los campos declarados.
    assert "4.0000" in reporte.titulo and "5.0000" in reporte.titulo


def test_el_reporte_guarda_quien_provoco_el_hecho(env):
    """`clave_actor` apunta al campo del payload que dice quién lo hizo."""
    s, ids = env
    reporte, _ = emision_uc.emitir(
        s,
        "sales.venta_anulada",
        {
            "venta_id": str(uuid.uuid4()),
            "sucursal_id": str(ids["sucursal"].id),
            "usuario_id": str(ids["cajero"].id),
        },
    )
    s.flush()
    assert reporte.actor_id == ids["cajero"].id


def test_un_hecho_del_sistema_se_guarda_sin_actor(env):
    """RN-REP-009: `sales.pedido_demorado` lo detecta un barrido. Ponerle el
    mozo que tomó el pedido sería acusarlo de una demora de cocina."""
    s, ids = env
    reporte, _ = emision_uc.emitir(
        s,
        "sales.pedido_demorado",
        {
            "venta_id": str(uuid.uuid4()),
            "sucursal_id": str(ids["sucursal"].id),
            "usuario_id": str(ids["cajero"].id),
            "minutos_umbral": 15,
            "minutos_transcurridos": 40,
            "estado": "en_cocina",
            "items_pendientes": 2,
        },
    )
    s.flush()
    assert reporte.actor_id is None


def test_un_actor_ausente_o_invalido_no_tumba_la_emision(env):
    """El listener corre post-commit sobre un hecho ya guardado: si esto
    lanzara, se perdería el reporte entero por un campo que faltó."""
    s, ids = env
    for payload_actor in ({}, {"usuario_id": "no-es-un-uuid"}):
        reporte, _ = emision_uc.emitir(
            s,
            "sales.venta_anulada",
            {
                "venta_id": str(uuid.uuid4()),
                "sucursal_id": str(ids["sucursal"].id),
                **payload_actor,
            },
        )
        s.flush()
        assert reporte.actor_id is None


def test_el_almacen_central_no_inventa_sucursal(env):
    s, ids = env
    reporte, _ = emision_uc.emitir(
        s,
        "inventory.stock_bajo_minimo",
        {
            "almacen_id": str(ids["alm_central"].id),
            "sku_id": str(uuid.uuid4()),
            "cantidad": "1", "stock_minimo": "5",
        },
    )
    s.flush()
    assert reporte.empresa_id == ids["empresa"].id
    assert reporte.sucursal_id is None


def test_un_hecho_que_no_se_puede_ubicar_se_emite_sin_empresa(env):
    """Se guarda igual: un reporte que no se pudo atribuir es justamente el
    que hay que poder investigar. Solo lo ve el superusuario."""
    s, _ = env
    reporte, destinatarios = emision_uc.emitir(
        s,
        "inventory.ajuste_fuera_margen",
        {"ajuste_id": str(uuid.uuid4()), "almacen_id": str(uuid.uuid4())},
    )
    s.flush()
    assert reporte.empresa_id is None
    assert destinatarios == []


def test_la_regla_de_la_sucursal_desplaza_a_la_general_al_emitir(env):
    s, ids = env
    _regla(
        s, ids, "sales.venta_anulada",
        [{"tipo": "rol", "rol_id": ids["rol_sup"].id}],
    )
    especifica = _regla(
        s, ids, "sales.venta_anulada",
        [{"tipo": "usuario", "usuario_id": ids["cajero"].id}],
        sucursal_id=ids["sucursal"].id,
        nivel="urgente",
    )

    reporte, destinatarios = emision_uc.emitir(
        s,
        "sales.venta_anulada",
        {
            "venta_id": str(uuid.uuid4()),
            "sucursal_id": str(ids["sucursal"].id),
            "usuario_id": str(ids["cajero"].id),
        },
    )
    s.flush()
    assert reporte.regla_id == especifica.id
    assert destinatarios == [ids["cajero"].id]
    # El nivel de la regla pisa el de la emisión.
    assert reporte.nivel == "urgente"


def test_cambiar_la_regla_no_reescribe_lo_ya_entregado(env):
    """RN-REP-004: la no retroactividad. Es la razón por la que la entrega
    guarda su motivo en vez de recalcularlo al leerse."""
    s, ids = env
    regla = _regla(
        s, ids, "inventory.ajuste_fuera_margen",
        [{"tipo": "area", "area_id": ids["area_almacen"].id}],
    )
    reporte, _ = emision_uc.emitir(
        s,
        "inventory.ajuste_fuera_margen",
        {"ajuste_id": str(uuid.uuid4()), "almacen_id": str(ids["alm_central"].id)},
    )
    s.commit()
    motivo_original = s.scalars(select(EntregaReporte)).all()[0].motivo

    reglas_uc.editar_regla(
        s,
        regla.id,
        destinatarios=[reglas_uc.DestinatarioIn(tipo="rol", rol_id=ids["rol_sup"].id)],
        actor_id=ids["supervisor1"].id,
    )
    s.commit()

    entregas = s.scalars(
        select(EntregaReporte).where(EntregaReporte.reporte_emitido_id == reporte.id)
    ).all()
    assert len(entregas) == 1
    assert entregas[0].usuario_id == ids["almacenero1"].id
    assert entregas[0].motivo == motivo_original


# --- Gobierno y auditoría -----------------------------------------------------
def test_crear_una_regla_deja_rastro_en_audit_log(env):
    """RN-REP-007: «si hay modificaciones en los flujos» se responde con
    `GET /api/v1/auditoria?entidad=regla_distribucion`, no con un historial
    propio en paralelo."""
    s, ids = env
    reglas_uc.crear_regla(
        s,
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        destinatarios=[
            reglas_uc.DestinatarioIn(tipo="area", area_id=ids["area_gerencia"].id)
        ],
        actor_id=ids["supervisor1"].id,
    )
    s.commit()
    fila = s.scalar(
        select(AuditLog).where(AuditLog.entidad == "regla_distribucion")
    )
    assert fila.accion == "crear"
    assert fila.usuario_id == ids["supervisor1"].id
    assert fila.datos_despues["codigo_emision"] == "sales.venta_anulada"


def test_editar_una_regla_guarda_el_antes_y_el_despues(env):
    s, ids = env
    regla = reglas_uc.crear_regla(
        s,
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        nivel="aviso",
        destinatarios=[],
        actor_id=ids["supervisor1"].id,
    )
    s.commit()
    reglas_uc.editar_regla(
        s, regla.id, nivel="urgente", actor_id=ids["supervisor1"].id
    )
    s.commit()

    fila = s.scalar(
        select(AuditLog)
        .where(AuditLog.entidad == "regla_distribucion", AuditLog.accion == "editar")
    )
    assert fila.datos_antes["nivel"] == "aviso"
    assert fila.datos_despues["nivel"] == "urgente"


def test_una_regla_no_puede_apuntar_a_una_emision_inexistente(env):
    """RN-REP-001: si pudiera, quedaría muda para siempre sin que nadie se
    entere."""
    s, ids = env
    with pytest.raises(reglas_uc.ReglaNegocio, match="catálogo de emisiones"):
        reglas_uc.crear_regla(
            s,
            empresa_id=ids["empresa"].id,
            codigo_emision="inventory.el_evento_que_no_existe",
            actor_id=ids["supervisor1"].id,
        )


def test_un_dinamico_desconocido_se_rechaza(env):
    s, ids = env
    with pytest.raises(reglas_uc.ReglaNegocio, match="dinámico desconocido"):
        reglas_uc.crear_regla(
            s,
            empresa_id=ids["empresa"].id,
            codigo_emision="sales.venta_anulada",
            destinatarios=[
                reglas_uc.DestinatarioIn(tipo="dinamico", dinamico="el_que_sea")
            ],
            actor_id=ids["supervisor1"].id,
        )


def test_no_se_pueden_crear_dos_reglas_en_el_mismo_ambito(env):
    """RN-REP-008: el hecho se entregaría dos veces."""
    s, ids = env
    reglas_uc.crear_regla(
        s,
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        actor_id=ids["supervisor1"].id,
    )
    s.flush()
    with pytest.raises(reglas_uc.Conflicto, match="RN-REP-008"):
        reglas_uc.crear_regla(
            s,
            empresa_id=ids["empresa"].id,
            codigo_emision="sales.venta_anulada",
            actor_id=ids["supervisor1"].id,
        )


def test_un_area_de_otra_empresa_no_puede_ser_destinataria(env):
    """RN-REP-006."""
    s, ids = env
    otro_grupo = Grupo(nombre="Otro")
    s.add(otro_grupo)
    s.flush()
    otra_empresa = Empresa(
        grupo_id=otro_grupo.id, razon_social="Otra SAC", ruc="20100000002",
        domicilio_fiscal="Jr. Z 1", tipo="operativa",
    )
    s.add(otra_empresa)
    s.flush()
    area_ajena = Area(empresa_id=otra_empresa.id, codigo="gerencia", nombre="Gerencia")
    s.add(area_ajena)
    s.flush()

    with pytest.raises(reglas_uc.ReglaNegocio, match="no pertenece a la empresa"):
        reglas_uc.crear_regla(
            s,
            empresa_id=ids["empresa"].id,
            codigo_emision="sales.venta_anulada",
            destinatarios=[
                reglas_uc.DestinatarioIn(tipo="area", area_id=area_ajena.id)
            ],
            actor_id=ids["supervisor1"].id,
        )


# =============================================================================
# API: permisos, doble puerta y aislamiento de tenant.
# =============================================================================
@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from src.seeders.seed import seed

    with Sesion() as s:
        seed(s)
        empresa = s.scalar(select(Empresa))
        sucursal = s.scalar(select(Sucursal))
        almacen = s.scalar(select(Almacen).where(Almacen.sucursal_id.is_(None)))
        s.commit()
        ids = {"empresa": empresa, "sucursal": sucursal, "almacen": almacen}

        def _override():
            yield s

        app = create_app()
        app.dependency_overrides[get_db] = _override
        with TestClient(app) as c:
            r = c.post(
                "/api/v1/auth/login", json={"username": "admin", "pin": "123456"}
            )
            c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
            yield c, s, ids


def test_el_seeder_deja_la_matriz_sin_huecos(api):
    """Si el módulo arrancara con la matriz vacía, los trece hechos
    ocurrirían sin llegarle a nadie."""
    c, _, _ = api
    matriz = c.get("/api/v1/reports/matriz").json()
    assert len(matriz) == len(catalogo.CATALOGO)
    huecos = [f["codigo"] for f in matriz if f["hueco"]]
    assert huecos == []


def test_la_matriz_dice_a_quien_llega_cada_hecho(api):
    c, _, _ = api
    matriz = {f["codigo"]: f for f in c.get("/api/v1/reports/matriz").json()}
    fila = matriz["inventory.conteo_vencido"]
    (regla,) = fila["reglas"]
    etiquetas = {d["etiqueta"] for d in regla["destinatarios"]}
    # RN-INV-021 lo dirige a almacén y gerencia, y el evento ya publicaba
    # `dirigido_a: ["almacen","gerencia"]` sin que nadie lo consumiera.
    assert etiquetas == {"Almacén", "Gerencia"}
    assert regla["sucursal"] == "Todas"


def test_una_regla_sin_destinatarios_sale_como_fuga(api):
    c, _, ids = api
    reglas = c.get(
        "/api/v1/reports/reglas", params={"codigo_emision": "sales.venta_anulada"}
    ).json()
    c.patch(f"/api/v1/reports/reglas/{reglas[0]['id']}", json={"destinatarios": []})

    matriz = {f["codigo"]: f for f in c.get("/api/v1/reports/matriz").json()}
    (regla,) = matriz["sales.venta_anulada"]["reglas"]
    assert regla["fuga"] is True
    assert regla["alcance"] == 0


def test_el_catalogo_de_emisiones_se_recorta_por_permiso(api):
    """Mismo criterio que `core/reportes`: el catálogo es una lista de
    capacidades y mostrar lo que después daría 403 solo confunde."""
    c, s, _ = api
    # El admin (comodín `*`) las ve todas.
    assert len(c.get("/api/v1/reports/emisiones").json()["emisiones"]) == len(
        catalogo.CATALOGO
    )

    # Con `inventory.leer` se ven las de inventario; `reports.leer` además
    # abre la cadena de escalamiento, que es del propio módulo.
    permisos = {"reports.leer", "inventory.leer"}
    visibles = catalogo.visibles(permisos)
    assert visibles and all(e.permiso in permisos for e in visibles)
    assert not any(e.permiso == "sales.leer" for e in visibles)

    solo_inventario = catalogo.visibles({"inventory.leer"})
    assert solo_inventario
    assert all(e.permiso == "inventory.leer" for e in solo_inventario)


def test_sin_permiso_no_se_ve_la_matriz(api):
    c, s, _ = api
    usuario = Usuario(username="raso", pin_hash=hash_pin("654321"), tipo="humano")
    s.add(usuario)
    s.flush()
    rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
    s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    s.add(
        UsuarioSucursal(
            usuario_id=usuario.id, sucursal_id=s.scalar(select(Sucursal)).id
        )
    )
    s.commit()

    r = c.post("/api/v1/auth/login", json={"username": "raso", "pin": "654321"})
    token = r.json()["access_token"]
    cabeceras = {"Authorization": f"Bearer {token}"}

    # `reports.leer` sí (es destinatario potencial); la matriz no.
    assert c.get("/api/v1/reports/mios", headers=cabeceras).status_code == 200
    assert c.get("/api/v1/reports/matriz", headers=cabeceras).status_code == 403
    assert c.get("/api/v1/reports/emitidos", headers=cabeceras).status_code == 403
    assert (
        c.post(
            "/api/v1/reports/areas",
            json={"codigo": "x", "nombre": "X"},
            headers=cabeceras,
        ).status_code
        == 403
    )


def test_ser_destinatario_no_alcanza_para_ver_el_contenido(api):
    """RN-REP-002, la segunda puerta. Un cocinero puede estar en la lista de
    un descuadre de caja y no tener `accounting.leer`: se entera de que pasó,
    no del detalle."""
    c, s, ids = api
    usuario = Usuario(username="raso2", pin_hash=hash_pin("654321"), tipo="humano")
    s.add(usuario)
    s.flush()
    rol = s.scalar(select(Rol).where(Rol.nombre == "cocinero"))
    s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=ids["sucursal"].id))

    reporte = ReporteEmitido(
        empresa_id=ids["empresa"].id,
        sucursal_id=ids["sucursal"].id,
        codigo_emision="accounting.cierre_caja_irregular",
        titulo="Cierre de caja irregular: descuadre de 40.00",
        nivel="urgente",
        datos={"descuadre_monto": "40.00"},
    )
    s.add(reporte)
    s.flush()
    s.add(
        EntregaReporte(
            reporte_emitido_id=reporte.id, usuario_id=usuario.id, motivo="rol:cocinero"
        )
    )
    s.commit()

    r = c.post("/api/v1/auth/login", json={"username": "raso2", "pin": "654321"})
    cabeceras = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Le fue entregado: aparece en su bandeja...
    mios = c.get("/api/v1/reports/mios", headers=cabeceras).json()
    assert [m["id"] for m in mios["items"]] == [str(reporte.id)]
    # ...pero el detalle exige `accounting.leer`, que un cocinero no tiene.
    detalle = c.get(f"/api/v1/reports/emitidos/{reporte.id}", headers=cabeceras)
    assert detalle.status_code == 403


def test_un_reporte_ajeno_responde_404_y_no_confirma_que_existe(api):
    c, s, ids = api
    usuario = Usuario(username="raso3", pin_hash=hash_pin("654321"), tipo="humano")
    s.add(usuario)
    s.flush()
    rol = s.scalar(select(Rol).where(Rol.nombre == "supervisor"))
    s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    s.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=ids["sucursal"].id))
    reporte = ReporteEmitido(
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        titulo="Venta anulada",
        datos={},
    )
    s.add(reporte)
    s.commit()

    r = c.post("/api/v1/auth/login", json={"username": "raso3", "pin": "654321"})
    cabeceras = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Tiene `sales.leer` y `reports.leer`, pero no es destinatario ni tiene
    # `reports.leer_todo`: mismo 404 que si no existiera.
    assert (
        c.get(f"/api/v1/reports/emitidos/{reporte.id}", headers=cabeceras).status_code
        == 404
    )


def test_el_detalle_dice_quien_lo_recibio_y_por_que(api):
    """El «por qué» es lo que le dice al administrador qué tocar para
    cambiarlo."""
    c, s, ids = api
    admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
    reporte = ReporteEmitido(
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        titulo="Venta anulada",
        datos={"venta_id": "x"},
    )
    s.add(reporte)
    s.flush()
    s.add(
        EntregaReporte(
            reporte_emitido_id=reporte.id,
            usuario_id=admin.id,
            motivo="area:gerencia",
        )
    )
    s.commit()

    detalle = c.get(f"/api/v1/reports/emitidos/{reporte.id}").json()
    assert detalle["datos"] == {"venta_id": "x"}
    assert detalle["entregas"] == [
        {
            "usuario_id": str(admin.id),
            "usuario": "admin",
            "motivo": "area:gerencia",
            "canal": "bandeja",
        }
    ]


def test_la_api_nombra_al_actor_y_dice_sistema_cuando_no_lo_hay(api):
    """Un hueco en «quién» obliga a salir del ERP a averiguarlo, que es
    justamente lo que el reporte tenía que evitar."""
    c, s, ids = api
    admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
    con_actor = ReporteEmitido(
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.venta_anulada",
        titulo="Venta anulada",
        datos={},
        actor_id=admin.id,
    )
    del_sistema = ReporteEmitido(
        empresa_id=ids["empresa"].id,
        codigo_emision="sales.pedido_demorado",
        titulo="Pedido demorado",
        datos={},
    )
    s.add_all([con_actor, del_sistema])
    s.commit()

    por_id = {
        r["id"]: r for r in c.get("/api/v1/reports/emitidos").json()["items"]
    }
    assert por_id[str(con_actor.id)]["actor"] == "admin"
    assert por_id[str(con_actor.id)]["actor_id"] == str(admin.id)
    assert por_id[str(del_sistema.id)]["actor"] == "Sistema"
    assert por_id[str(del_sistema.id)]["actor_id"] is None

    detalle = c.get(f"/api/v1/reports/emitidos/{con_actor.id}").json()
    assert detalle["actor"] == "admin"


def test_no_existe_endpoint_para_escribir_un_reporte(api):
    """El reporte lo emite el evento, no un cliente — mismo criterio que
    ADR-031 para `audit_log`."""
    c, _, _ = api
    assert c.post("/api/v1/reports/emitidos", json={}).status_code == 405


def test_administrar_areas_y_miembros_de_punta_a_punta(api):
    c, s, ids = api
    creada = c.post(
        "/api/v1/reports/areas", json={"codigo": "auditoria", "nombre": "Auditoría"}
    )
    assert creada.status_code == 201
    area_id = creada.json()["id"]

    rol = s.scalar(select(Rol).where(Rol.nombre == "contador"))
    miembro = c.post(
        f"/api/v1/reports/areas/{area_id}/miembros", json={"rol_id": str(rol.id)}
    )
    assert miembro.status_code == 201
    assert len(c.get(f"/api/v1/reports/areas/{area_id}/miembros").json()) == 1

    # Un miembro no puede ser rol *y* usuario a la vez.
    admin = s.scalar(select(Usuario).where(Usuario.username == "admin"))
    invalido = c.post(
        f"/api/v1/reports/areas/{area_id}/miembros",
        json={"rol_id": str(rol.id), "usuario_id": str(admin.id)},
    )
    assert invalido.status_code == 409

    assert (
        c.delete(
            f"/api/v1/reports/areas/{area_id}/miembros/{miembro.json()['id']}"
        ).status_code
        == 204
    )
    assert c.delete(f"/api/v1/reports/areas/{area_id}").status_code == 204


def test_un_area_en_uso_no_se_borra(api):
    """Borrarla dejaría la regla apuntando a la nada y el hecho pasaría a no
    llegarle a nadie sin que nadie lo haya decidido."""
    c, s, _ = api
    area = s.scalar(select(Area).where(Area.codigo == "gerencia"))
    r = c.delete(f"/api/v1/reports/areas/{area.id}")
    assert r.status_code == 409
    assert "desactivarla" in r.json()["detail"]


def test_el_codigo_de_area_no_admite_cualquier_cosa(api):
    c, _, _ = api
    assert (
        c.post(
            "/api/v1/reports/areas", json={"codigo": "Con Espacios", "nombre": "X"}
        ).status_code
        == 422
    )
