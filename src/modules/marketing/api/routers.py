"""Routers FastAPI del módulo marketing: campaña, contenido, lead, encuesta y
evaluación de agencia.

Sin `try/except … raise _http(e)`: los errores de aplicación heredan de
`src/shared/errors.py` y `src/core/error_handlers.py` los traduce a HTTP una
sola vez para todo el ERP.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.marketing.api import schemas
from src.modules.marketing.application import (
    adjuntos as adjuntos_uc,
)
from src.modules.marketing.application import (
    agencias,
    campanas,
    contenido,
    encuestas,
    leads,
    metricas,
    plantillas,
)
from src.modules.marketing.application.errors import NoEncontrado
from src.modules.marketing.application.scope import (
    exigir_campana,
    exigir_encuesta,
    exigir_evaluacion,
    exigir_lead,
    exigir_pieza,
    exigir_plantilla,
    exigir_sucursal,
)
from src.modules.marketing.infrastructure.repositories import (
    CampanaRepo,
    EncuestaPlantillaRepo,
    EvaluacionAgenciaRepo,
    LeadRepo,
    PiezaContenidoRepo,
)
from src.modules.sales.application.queries_publicas import venta_para_encuesta
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/marketing", tags=["marketing"])

LEER = "marketing.leer"
CAMPANA_GESTIONAR = "marketing.campana_gestionar"
CAMPANA_APROBAR = "marketing.campana_aprobar"
CONTENIDO_GESTIONAR = "marketing.contenido_gestionar"
LEAD_GESTIONAR = "marketing.lead_gestionar"
ENCUESTA_GESTIONAR = "marketing.encuesta_gestionar"
AGENCIA_EVALUAR = "marketing.agencia_evaluar"
AGENCIA_DECIDIR = "marketing.agencia_decidir"

# Ventana por defecto del calendario de contenido cuando no se pide rango.
DIAS_CALENDARIO = 30


# --- Campaña ---------------------------------------------------------------


@router.post("/campanas", response_model=schemas.CampanaOut, status_code=201)
def crear_campana(
    body: schemas.CampanaCreate,
    actor: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campana = campanas.crear_campana(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        marca_id=body.marca_id,
        nombre=body.nombre,
        tipo=body.tipo,
        canal=body.canal,
        objetivo=body.objetivo,
        publico_objetivo=body.publico_objetivo,
        presupuesto=body.presupuesto,
        kpi=body.kpi,
        creado_por=actor.id,
        idempotency_key=body.idempotency_key,
    )
    session.commit()
    return campana


@router.get("/campanas", response_model=Pagina[schemas.CampanaOut])
def listar_campanas(
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        CampanaRepo(session).q_listar(tenant.filtro_empresa(), estado=estado),
        p,
    )


@router.get("/campanas/{campana_id}", response_model=schemas.CampanaOut)
def ver_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_campana(session, campana_id, tenant)


@router.get("/campanas/{campana_id}/metricas", response_model=schemas.MetricaCampanaOut)
def ver_metricas(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Acumulado que mantienen los listeners del propio módulo. Un cero acá
    no es "no hay datos": es que todavía no pasó nada de eso."""
    exigir_campana(session, campana_id, tenant)
    return metricas.resumen(session, campana_id)


@router.post(
    "/campanas/{campana_id}/metricas/recalculo",
    response_model=schemas.MetricaCampanaOut,
)
def recalcular_metricas(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Rehace el acumulado desde las tablas. Existe porque el acumulado se
    mantiene por eventos: un worker caído deja el contador corto y sin esto
    no habría forma de corregirlo."""
    exigir_campana(session, campana_id, tenant)
    metricas.recalcular(session, campana_id)
    session.commit()
    return metricas.resumen(session, campana_id)


@router.patch("/campanas/{campana_id}/brief", response_model=schemas.CampanaOut)
def completar_brief(
    campana_id: uuid.UUID,
    body: schemas.BriefUpdate,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    campana = campanas.completar_brief(
        session,
        campana_id,
        objetivo=body.objetivo,
        publico_objetivo=body.publico_objetivo,
        presupuesto=body.presupuesto,
        kpi=body.kpi,
    )
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/aprobacion", response_model=schemas.CampanaOut)
def aprobar_campana(
    campana_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(CAMPANA_APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    campana = campanas.aprobar_campana(session, campana_id, aprobada_por=actor.id)
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/lanzamiento", response_model=schemas.CampanaOut)
def lanzar_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    campana = campanas.lanzar_campana(session, campana_id)
    session.commit()
    return campana


@router.post("/campanas/{campana_id}/cierre", response_model=schemas.CampanaOut)
def cerrar_campana(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    campana = campanas.cerrar_campana(session, campana_id)
    session.commit()
    return campana


@router.post(
    "/campanas/{campana_id}/implementaciones",
    response_model=schemas.ImplementacionOut,
    status_code=201,
)
def registrar_implementacion(
    campana_id: uuid.UUID,
    body: schemas.ImplementacionCreate,
    actor: Usuario = Depends(require_permission(CAMPANA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    exigir_sucursal(session, body.sucursal_id, tenant)
    registro = campanas.registrar_implementacion_material(
        session,
        campana_id,
        sucursal_id=body.sucursal_id,
        verificado_por=actor.id,
        completa=body.completa,
        incidencia=body.incidencia,
        fecha=body.fecha,
    )
    session.commit()
    return registro


# --- Evaluación de agencia (RN-MKT-006) --------------------------------------


@router.post(
    "/campanas/{campana_id}/evaluaciones-agencia",
    response_model=schemas.EvaluacionOut,
    status_code=201,
)
def crear_evaluacion_agencia(
    campana_id: uuid.UUID,
    body: schemas.EvaluacionCreate,
    actor: Usuario = Depends(require_permission(AGENCIA_EVALUAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    evaluacion = agencias.crear_evaluacion(
        session,
        campana_id=campana_id,
        objetivo=body.objetivo,
        presupuesto_referencia=body.presupuesto_referencia,
        criterios=[c.model_dump(mode="json") for c in body.criterios],
        creado_por=actor.id,
    )
    session.commit()
    return evaluacion


@router.get(
    "/campanas/{campana_id}/evaluaciones-agencia",
    response_model=Pagina[schemas.EvaluacionOut],
)
def listar_evaluaciones_agencia(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    return paginar(session, EvaluacionAgenciaRepo(session).q_de_campana(campana_id), p)


@router.get(
    "/evaluaciones-agencia/{evaluacion_id}",
    response_model=schemas.EvaluacionConSugerenciaOut,
)
def ver_evaluacion_agencia(
    evaluacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    evaluacion = exigir_evaluacion(session, evaluacion_id, tenant)
    sugerida = agencias.recomendada(evaluacion)
    return {
        "evaluacion": evaluacion,
        "opcion_recomendada_id": uuid.UUID(sugerida.id) if sugerida else None,
    }


@router.post(
    "/evaluaciones-agencia/{evaluacion_id}/opciones",
    response_model=schemas.OpcionOut,
    status_code=201,
)
def agregar_opcion_agencia(
    evaluacion_id: uuid.UUID,
    body: schemas.OpcionCreate,
    _: Usuario = Depends(require_permission(AGENCIA_EVALUAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_evaluacion(session, evaluacion_id, tenant)
    opcion = agencias.agregar_opcion(
        session,
        evaluacion_id,
        tipo=body.tipo,
        nombre=body.nombre,
        costo=body.costo,
        plazo_dias=body.plazo_dias,
        puntajes=body.puntajes,
        proveedor_id=body.proveedor_id,
        observacion=body.observacion,
    )
    session.commit()
    return opcion


@router.post(
    "/evaluaciones-agencia/{evaluacion_id}/cierre",
    response_model=schemas.EvaluacionConSugerenciaOut,
)
def cerrar_evaluacion_agencia(
    evaluacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(AGENCIA_EVALUAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_evaluacion(session, evaluacion_id, tenant)
    evaluacion = agencias.cerrar_evaluacion(session, evaluacion_id)
    session.commit()
    sugerida = agencias.recomendada(evaluacion)
    return {
        "evaluacion": evaluacion,
        "opcion_recomendada_id": uuid.UUID(sugerida.id) if sugerida else None,
    }


@router.post(
    "/evaluaciones-agencia/{evaluacion_id}/decision",
    response_model=schemas.EvaluacionOut,
)
def decidir_agencia(
    evaluacion_id: uuid.UUID,
    body: schemas.DecisionAgencia,
    actor: Usuario = Depends(require_permission(AGENCIA_DECIDIR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Gerencia valida: permiso distinto del de evaluar a propósito — quien
    arma la comparación no la firma (RN-MKT-006, RN-GER-007)."""
    exigir_evaluacion(session, evaluacion_id, tenant)
    evaluacion = agencias.decidir(
        session,
        evaluacion_id,
        opcion_id=body.opcion_id,
        decidida_por=actor.id,
        motivo=body.motivo,
    )
    session.commit()
    return evaluacion


# --- Contenido -------------------------------------------------------------


@router.post("/piezas", response_model=schemas.PiezaOut, status_code=201)
def planificar_pieza(
    body: schemas.PiezaCreate,
    actor: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if body.campana_id is not None:
        exigir_campana(session, body.campana_id, tenant)
    pieza = contenido.planificar_pieza(
        session,
        marca_id=body.marca_id,
        titulo=body.titulo,
        canal=body.canal,
        fecha_publicacion=body.fecha_publicacion,
        campana_id=body.campana_id,
        pertinente_marca=body.pertinente_marca,
        uso_marca_validado=body.uso_marca_validado,
        creado_por=actor.id,
    )
    session.commit()
    return pieza


@router.get("/piezas/calendario", response_model=schemas.CalendarioOut)
def calendario_contenido(
    desde: date | None = None,
    hasta: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El calendario de contenido: qué se publica cada día y con qué arte.

    Agrupado por fecha y no paginado a propósito — un calendario partido en
    páginas deja de ser un calendario. El rango lo acota (30 días por
    defecto), que es el límite real de lo que alguien mira de una vez.
    """
    desde = desde or fechas.hoy()
    hasta = hasta or date.fromordinal(desde.toordinal() + DIAS_CALENDARIO)
    campanas_tenant = CampanaRepo(session).listar(tenant.filtro_empresa())
    piezas = PiezaContenidoRepo(session).del_rango(
        [c.id for c in campanas_tenant], desde, hasta
    )
    conteo = adjuntos_uc.conteo_por_pieza(session, [p.id for p in piezas])

    dias: dict[date, list] = {}
    for pieza in piezas:
        fila = schemas.PiezaCalendarioOut(
            **schemas.PiezaOut.model_validate(pieza, from_attributes=True).model_dump(),
            adjuntos=conteo.get(pieza.id, 0),
        )
        dias.setdefault(pieza.fecha_publicacion, []).append(fila)
    return {
        "desde": desde,
        "hasta": hasta,
        "dias": [{"fecha": f, "piezas": dias[f]} for f in sorted(dias)],
    }


@router.get("/piezas", response_model=Pagina[schemas.PiezaOut])
def listar_piezas(
    estado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Listado plano del calendario de contenido del tenant."""
    campanas_tenant = CampanaRepo(session).listar(tenant.filtro_empresa())
    return paginar(
        session,
        PiezaContenidoRepo(session).q_listar(
            [c.id for c in campanas_tenant], estado, desde, hasta
        ),
        p,
    )


@router.patch("/piezas/{pieza_id}/validacion", response_model=schemas.PiezaOut)
def validar_pieza(
    pieza_id: uuid.UUID,
    body: schemas.PiezaValidar,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pieza(session, pieza_id, tenant)
    pieza = contenido.validar_pieza(
        session,
        pieza_id,
        pertinente_marca=body.pertinente_marca,
        uso_marca_validado=body.uso_marca_validado,
    )
    session.commit()
    return pieza


@router.post("/piezas/{pieza_id}/publicacion", response_model=schemas.PiezaOut)
def publicar_pieza(
    pieza_id: uuid.UUID,
    body: schemas.PiezaPublicar,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pieza(session, pieza_id, tenant)
    pieza = contenido.publicar_pieza(session, pieza_id, metricas=body.metricas)
    session.commit()
    return pieza


@router.post("/piezas/{pieza_id}/descarte", response_model=schemas.PiezaOut)
def descartar_pieza(
    pieza_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pieza(session, pieza_id, tenant)
    pieza = contenido.descartar_pieza(session, pieza_id)
    session.commit()
    return pieza


@router.post(
    "/piezas/{pieza_id}/adjuntos", response_model=schemas.AdjuntoOut, status_code=201
)
def adjuntar_a_pieza(
    pieza_id: uuid.UUID,
    body: schemas.AdjuntoCreate,
    actor: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Registra el arte ya subido al storage. El ERP guarda el vínculo y los
    metadatos; el binario viaja directo a S3 y nunca pasa por la API."""
    exigir_pieza(session, pieza_id, tenant)
    archivo = adjuntos_uc.adjuntar(
        session,
        pieza_id,
        nombre=body.nombre,
        mime_type=body.mime_type,
        tamano_bytes=body.tamano_bytes,
        url_storage=body.url_storage,
        subido_por=actor.id,
    )
    session.commit()
    return archivo


@router.get("/piezas/{pieza_id}/adjuntos", response_model=list[schemas.AdjuntoOut])
def listar_adjuntos(
    pieza_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pieza(session, pieza_id, tenant)
    return adjuntos_uc.listar(session, pieza_id)


@router.delete("/piezas/{pieza_id}/adjuntos/{archivo_id}", status_code=204)
def quitar_adjunto(
    pieza_id: uuid.UUID,
    archivo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONTENIDO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pieza(session, pieza_id, tenant)
    adjuntos_uc.quitar(session, pieza_id, archivo_id)
    session.commit()


# --- Lead ------------------------------------------------------------------


@router.post("/leads", response_model=schemas.LeadOut, status_code=201)
def registrar_lead(
    body: schemas.LeadCreate,
    _: Usuario = Depends(require_permission(LEAD_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_campana(session, body.campana_id, tenant)
    lead = leads.registrar_lead(
        session,
        campana_id=body.campana_id,
        canal=body.canal,
        tipo=body.tipo,
        contacto=body.contacto,
        cliente_id=body.cliente_id,
        idempotency_key=body.idempotency_key,
    )
    session.commit()
    return lead


@router.get("/campanas/{campana_id}/leads", response_model=Pagina[schemas.LeadOut])
def listar_leads(
    campana_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    exigir_campana(session, campana_id, tenant)
    return paginar(session, LeadRepo(session).q_de_campana(campana_id), p)


@router.post("/leads/{lead_id}/atribucion", response_model=schemas.LeadOut)
def atribuir_lead(
    lead_id: uuid.UUID,
    body: schemas.LeadAtribuir,
    _: Usuario = Depends(require_permission(LEAD_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_lead(session, lead_id, tenant)
    venta = venta_para_encuesta(session, body.venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    exigir_sucursal(session, venta["sucursal_id"], tenant)
    lead = leads.atribuir_venta(session, lead_id, venta_id=body.venta_id)
    session.commit()
    return lead


# --- Plantilla de encuesta (el guion) ---------------------------------------
# Antes de `/encuestas/{encuesta_id}`: FastAPI resuelve por orden y
# "plantillas" se comería como UUID inválido.


@router.post(
    "/encuestas/plantillas", response_model=schemas.PlantillaDetalleOut, status_code=201
)
def crear_plantilla(
    body: schemas.PlantillaCreate,
    actor: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    plantilla = plantillas.crear_plantilla(
        session,
        empresa_id=tenant.empresa(body.empresa_id),
        nombre=body.nombre,
        saludo=body.saludo,
        despedida=body.despedida,
        preguntas=[p.model_dump(mode="json") for p in body.preguntas],
        creado_por=actor.id,
        marca_id=body.marca_id,
        activa=body.activa,
    )
    session.commit()
    return _plantilla_detalle(session, plantilla)


@router.get("/encuestas/plantillas", response_model=Pagina[schemas.PlantillaOut])
def listar_plantillas(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session, EncuestaPlantillaRepo(session).q_listar(tenant.filtro_empresa()), p
    )


@router.get(
    "/encuestas/plantillas/{plantilla_id}", response_model=schemas.PlantillaDetalleOut
)
def ver_plantilla(
    plantilla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return _plantilla_detalle(session, exigir_plantilla(session, plantilla_id, tenant))


@router.post(
    "/encuestas/plantillas/{plantilla_id}/activacion",
    response_model=schemas.PlantillaOut,
)
def activar_plantilla(
    plantilla_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_plantilla(session, plantilla_id, tenant)
    plantilla = plantillas.activar(session, plantilla_id)
    session.commit()
    return plantilla


# --- Encuesta de satisfacción ----------------------------------------------


@router.post("/encuestas", response_model=schemas.EncuestaConNodoOut, status_code=201)
def enviar_encuesta(
    body: schemas.EncuestaCreate,
    actor: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Crea la encuesta y la deja en su primer nodo. El envío real sale por
    el listener de `marketing.encuesta_enviada`, ya commiteada (ADR-016)."""
    venta = venta_para_encuesta(session, body.venta_id)
    if venta is None:
        raise NoEncontrado("venta no encontrada")
    exigir_sucursal(session, venta["sucursal_id"], tenant)
    encuesta = encuestas.enviar_encuesta(
        session,
        venta_id=body.venta_id,
        canal=body.canal,
        enviada_por=actor.id,
        plantilla_id=body.plantilla_id,
    )
    session.commit()
    return _encuesta_con_nodo(session, encuesta)


@router.get("/encuestas/{encuesta_id}", response_model=schemas.EncuestaConNodoOut)
def ver_encuesta(
    encuesta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return _encuesta_con_nodo(session, exigir_encuesta(session, encuesta_id, tenant))


@router.post(
    "/encuestas/{encuesta_id}/respuesta", response_model=schemas.EncuestaConNodoOut
)
def responder_encuesta(
    encuesta_id: uuid.UUID,
    body: schemas.EncuestaRespuesta,
    _: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Contesta el nodo pendiente. Es la vía del canal `pos` —la tablet del
    local— y la de corregir a mano; WhatsApp entra por su webhook y el
    enlace público por `/marketing/publico`."""
    encuesta = exigir_encuesta(session, encuesta_id, tenant)
    encuestas.responder_nodo(session, encuesta, body.valor)
    session.commit()
    return _encuesta_con_nodo(session, encuesta)


@router.post("/encuestas/{encuesta_id}/expiracion", response_model=schemas.EncuestaOut)
def expirar_encuesta(
    encuesta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ENCUESTA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_encuesta(session, encuesta_id, tenant)
    encuesta = encuestas.expirar_encuesta(session, encuesta_id)
    session.commit()
    return encuesta


# --- Interno -----------------------------------------------------------------


def _encuesta_con_nodo(session: Session, encuesta) -> dict:
    return {
        "encuesta": encuesta,
        "pregunta_actual": encuestas.pregunta_actual(session, encuesta),
        "url_publica": encuestas.url_publica(encuesta),
    }


def _plantilla_detalle(session: Session, plantilla) -> dict:
    preguntas = EncuestaPlantillaRepo(session).preguntas_de(plantilla.id)
    return {
        **schemas.PlantillaOut.model_validate(plantilla, from_attributes=True).model_dump(),
        "preguntas": preguntas,
    }
