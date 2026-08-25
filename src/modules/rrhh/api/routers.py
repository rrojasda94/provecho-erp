"""Routers FastAPI del módulo rrhh: ciclo laboral completo."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.core.rate_limit import consumir, ip_de, rate_limit
from src.core.tenant import Tenant
from src.modules.rrhh.api import schemas
from src.modules.rrhh.application import (
    asistencia as asistencia_uc,
)
from src.modules.rrhh.application import (
    capacitacion,
    contratos,
    convocatorias,
    disciplina,
    nomina,
    pad_asistencia,
    permisos,
    postulantes,
    privacidad,
    socios,
    trabajadores,
    turnos,
)
from src.modules.rrhh.application import (
    legajo as legajo_uc,
)
from src.modules.rrhh.application.scope import (
    exigir_acta,
    exigir_amonestacion,
    exigir_boleta,
    exigir_certificado,
    exigir_contrato,
    exigir_convocatoria,
    exigir_liquidacion,
    exigir_memorandum,
    exigir_pacto,
    exigir_postulante,
    exigir_solicitud_permiso,
    exigir_trabajador,
    exigir_turno,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.application.queries_publicas import (
    PIN_BLOQUEADO,
    PIN_OK,
    tiene_permiso,
    verificar_pin_de,
)
from src.modules.users.infrastructure.models import Usuario
from src.shared import auditoria, fechas
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/rrhh", tags=["rrhh"])

LEER = "rrhh.leer"
TRABAJADOR_GESTIONAR = "rrhh.trabajador_gestionar"
CONTRATO_GESTIONAR = "rrhh.contrato_gestionar"
POSTULANTE_GESTIONAR = "rrhh.postulante_gestionar"
CONVOCATORIA_GESTIONAR = "rrhh.convocatoria_gestionar"
SOCIO_GESTIONAR = "rrhh.socio_gestionar"
NOMINA_GESTIONAR = "rrhh.nomina_gestionar"
DISCIPLINA_GESTIONAR = "rrhh.disciplina_gestionar"
PERMISO_SOLICITAR = "rrhh.permiso_solicitar"
PERMISO_APROBAR = "rrhh.permiso_aprobar"
ASISTENCIA_MARCAR = "rrhh.asistencia_marcar"
# Abrir el pad del local es otra cosa que corregir una marcación desde el
# back-office: el pad no marca por nadie, solo presenta la firma del
# trabajador (ADR-064).
ASISTENCIA_TERMINAL = "rrhh.asistencia_terminal"
TURNO_GESTIONAR = "rrhh.turno_gestionar"
CAPACITACION_GESTIONAR = "rrhh.capacitacion_gestionar"
# Misma capacidad legal que sobre `persona` (Ley 29733): un permiso nuevo
# solo agregaría matriz que mantener.
ANONIMIZAR = "personas.anonimizar"


# El formulario de postulación es público: sin límite, cualquiera llena la
# base de candidatos con basura. 20 por hora y por IP alcanza de sobra para
# una familia postulando desde la misma casa o cabina.
_rate_limit_postulacion = rate_limit("postulacion", 20, 3600)


# --- Trabajador ----------------------------------------------------------------
@router.post("/trabajadores", response_model=schemas.TrabajadorOut, status_code=201)
def crear_trabajador(
    body: schemas.TrabajadorCreate,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    trabajador = trabajadores.crear_trabajador(session, **campos)
    session.commit()
    return trabajador


@router.get("/trabajadores", response_model=Pagina[schemas.TrabajadorOut])
def listar_trabajadores(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        trabajadores.q_trabajadores(session, tenant.filtro_empresa(empresa_id)),
        p,
    )


@router.get("/trabajadores/{trabajador_id}", response_model=schemas.TrabajadorOut)
def ver_trabajador(
    trabajador_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_trabajador(session, trabajador_id, tenant)


@router.patch("/trabajadores/{trabajador_id}", response_model=schemas.TrabajadorOut)
def actualizar_trabajador(
    trabajador_id: uuid.UUID,
    body: schemas.TrabajadorUpdate,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, trabajador_id, tenant)
    # `exclude_unset`: lo que no vino no se toca, y un `sucursal_id: null`
    # explícito sí llega para poder borrar el centro de labores.
    trabajador = trabajadores.actualizar_trabajador(
        session, trabajador_id, **body.model_dump(exclude_unset=True)
    )
    session.commit()
    return trabajador


@router.post("/trabajadores/{trabajador_id}/cesar", response_model=schemas.TrabajadorOut)
def cesar_trabajador(
    trabajador_id: uuid.UUID,
    body: schemas.TrabajadorCese,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, trabajador_id, tenant)
    trabajador = trabajadores.cesar_trabajador(
        session, trabajador_id, fecha_cese=body.fecha_cese
    )
    session.commit()
    return trabajador


# --- Legajo del trabajador (file personal) -----------------------------------
@router.get("/trabajadores/{trabajador_id}/legajo", response_model=schemas.LegajoOut)
def ver_legajo(
    trabajador_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El expediente completo en una sola lectura: contratos, amonestaciones,
    memorándums, certificados, permisos y pactos.

    **La nómina va solo con `rrhh.nomina_gestionar`.** Boletas y
    liquidaciones llevan remuneración, y `rrhh.leer` lo tiene el supervisor,
    que necesita ver las amonestaciones de su gente pero no cuánto gana. Que
    una boleta ya fuera legible pidiéndola por su id no es razón para
    volverla navegable. Cuando no viaja, `nomina_visible` lo dice: un legajo
    sin sueldos no puede leerse igual que uno censurado.

    `asistencia` no entra acá — crece una fila por día y por trabajador, y
    se pide por `GET /rrhh/asistencia` acotada por rango.
    """
    exigir_trabajador(session, trabajador_id, tenant)
    return legajo_uc.legajo(
        session,
        trabajador_id,
        incluir_nomina=tiene_permiso(session, actor.id, NOMINA_GESTIONAR),
    )


@router.get(
    "/solicitudes-permiso", response_model=Pagina[schemas.SolicitudPermisoOut]
)
def listar_solicitudes_permiso(
    estado: str | None = None,
    trabajador_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Bandeja de aprobación. `estado=pendiente` es la vista que importa:
    quien aprueba entra por "qué tengo pendiente", no por un trabajador.
    Ordenadas por fecha de inicio ascendente — la que envejece sin respuesta
    es la que hay que atender."""
    if trabajador_id is not None:
        exigir_trabajador(session, trabajador_id, tenant)
    return paginar(
        session,
        legajo_uc.q_permisos(
            session,
            empresa_id=tenant.filtro_empresa(empresa_id),
            estado=estado,
            trabajador_id=trabajador_id,
        ),
        p,
    )


@router.get("/asistencia", response_model=Pagina[schemas.AsistenciaOut])
def listar_asistencia(
    trabajador_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Marcaciones del rango. Sin fechas, el mes en curso: pedir la
    asistencia entera de una empresa no es un caso de uso, es un accidente.
    """
    if trabajador_id is not None:
        exigir_trabajador(session, trabajador_id, tenant)
    hoy = fechas.hoy()
    desde = desde or hoy.replace(day=1)
    hasta = hasta or hoy
    if hasta < desde:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "`hasta` no puede ser anterior a `desde`"
        )
    return paginar(
        session,
        legajo_uc.q_asistencia(
            session,
            empresa_id=tenant.filtro_empresa(empresa_id),
            trabajador_id=trabajador_id,
            desde=desde,
            hasta=hasta,
        ),
        p,
    )


# --- Contrato laboral ------------------------------------------------------------
@router.post("/contratos-laborales", response_model=schemas.ContratoLaboralOut, status_code=201)
def crear_contrato_laboral(
    body: schemas.ContratoLaboralCreate,
    _: Usuario = Depends(require_permission(CONTRATO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    contrato = contratos.crear_contrato_laboral(session, **body.model_dump())
    session.commit()
    return contrato


@router.get("/contratos-laborales/{contrato_id}", response_model=schemas.ContratoLaboralOut)
def ver_contrato_laboral(
    contrato_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_contrato(session, contrato_id, tenant)


@router.post(
    "/contratos-laborales/{contrato_id}/firmar", response_model=schemas.ContratoLaboralOut
)
def firmar_contrato_laboral(
    contrato_id: uuid.UUID,
    body: schemas.ContratoLaboralFirmar,
    _: Usuario = Depends(require_permission(CONTRATO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_contrato(session, contrato_id, tenant)
    contrato = contratos.firmar_contrato_laboral(
        session, contrato_id, fecha_firma=body.fecha_firma
    )
    session.commit()
    return contrato


@router.post(
    "/contratos-laborales/{contrato_id}/finalizar", response_model=schemas.ContratoLaboralOut
)
def finalizar_contrato_laboral(
    contrato_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONTRATO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_contrato(session, contrato_id, tenant)
    contrato = contratos.finalizar_contrato_laboral(session, contrato_id)
    session.commit()
    return contrato


# --- Convocatoria ---------------------------------------------------------------
@router.post("/convocatorias", response_model=schemas.ConvocatoriaOut, status_code=201)
def crear_convocatoria(
    body: schemas.ConvocatoriaCreate,
    _: Usuario = Depends(require_permission(CONVOCATORIA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    if campos["sucursal_id"] is not None:
        tenant.exigir_sucursal(campos["sucursal_id"])
    convocatoria = convocatorias.crear_convocatoria(session, **campos)
    session.commit()
    return convocatoria


@router.get("/convocatorias", response_model=list[schemas.ConvocatoriaOut])
def listar_convocatorias(
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return convocatorias.listar_convocatorias(
        session, tenant.filtro_empresa(empresa_id), estado
    )


@router.get("/convocatorias/{convocatoria_id}", response_model=schemas.ConvocatoriaOut)
def ver_convocatoria(
    convocatoria_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_convocatoria(session, convocatoria_id, tenant)


@router.post(
    "/convocatorias/{convocatoria_id}/publicar", response_model=schemas.ConvocatoriaOut
)
def publicar_convocatoria(
    convocatoria_id: uuid.UUID,
    body: schemas.ConvocatoriaPublicar,
    _: Usuario = Depends(require_permission(CONVOCATORIA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_convocatoria(session, convocatoria_id, tenant)
    convocatoria = convocatorias.publicar_convocatoria(
        session, convocatoria_id, **body.model_dump()
    )
    session.commit()
    return convocatoria


@router.post(
    "/convocatorias/{convocatoria_id}/cerrar", response_model=schemas.ConvocatoriaOut
)
def cerrar_convocatoria(
    convocatoria_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CONVOCATORIA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_convocatoria(session, convocatoria_id, tenant)
    convocatoria = convocatorias.cerrar_convocatoria(session, convocatoria_id)
    session.commit()
    return convocatoria


@router.get(
    "/convocatorias/{convocatoria_id}/tablero", response_model=list[schemas.TableroColumna]
)
def ver_tablero(
    convocatoria_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Columnas del proceso de contratación en orden, con sus fichas."""
    exigir_convocatoria(session, convocatoria_id, tenant)
    return convocatorias.tablero(session, convocatoria_id)


# --- Postulante --------------------------------------------------------------
@router.post(
    "/postulaciones/{token}",
    response_model=schemas.PostulanteOut,
    status_code=201,
    dependencies=[Depends(_rate_limit_postulacion)],
)
def recibir_postulacion(
    token: str,
    body: schemas.PostulacionPublica,
    session: Session = Depends(get_db),
):
    """Endpoint público del formulario de postulación (Google Forms vía Apps
    Script, o cualquier formulario propio). Sin JWT: el token de la
    convocatoria publicada es lo único que autoriza a escribir, y solo puede
    crear un postulante."""
    postulante = postulantes.recibir_postulacion(
        session, token=token, fecha_postulacion=fechas.hoy(), **body.model_dump()
    )
    session.commit()
    return postulante


@router.post("/postulantes", response_model=schemas.PostulanteOut, status_code=201)
def crear_postulante(
    body: schemas.PostulanteCreate,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    postulante = postulantes.crear_postulante(session, **campos)
    session.commit()
    return postulante


@router.get("/postulantes", response_model=Pagina[schemas.PostulanteOut])
def listar_postulantes(
    estado: str | None = None,
    convocatoria_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session,
        postulantes.q_postulantes(
            session, estado, tenant.filtro_empresa(), convocatoria_id
        ),
        p,
    )


@router.get("/postulantes/{postulante_id}", response_model=schemas.PostulanteOut)
def ver_postulante(
    postulante_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Acceso (ARCO): el titular lo ejerce a través de quien administra el
    ERP, igual que en `personas` (ADR-011)."""
    return exigir_postulante(session, postulante_id, tenant)


@router.patch("/postulantes/{postulante_id}", response_model=schemas.PostulanteOut)
def actualizar_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteUpdate,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Rectificación (ARCO)."""
    exigir_postulante(session, postulante_id, tenant)
    postulante = postulantes.actualizar_postulante(
        session, postulante_id, **body.model_dump()
    )
    session.commit()
    return postulante


@router.post("/postulantes/{postulante_id}/anonimizar", response_model=schemas.PostulanteOut)
def anonimizar_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteAnonimizar,
    actor: Usuario = Depends(require_permission(ANONIMIZAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cancelación (ARCO, Ley 29733). Irreversible. Reusa el permiso
    `personas.anonimizar`: es la misma capacidad legal y el mismo custodio,
    aunque la tabla sea otra."""
    exigir_postulante(session, postulante_id, tenant)
    postulante = privacidad.anonimizar_postulante(
        session, postulante_id, motivo=body.motivo, solicitado_por=actor.id
    )
    session.commit()
    return postulante


@router.post("/postulantes/{postulante_id}/avanzar", response_model=schemas.PostulanteOut)
def avanzar_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteAvanzar,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_postulante(session, postulante_id, tenant)
    postulante = postulantes.avanzar_postulante(session, postulante_id, estado=body.estado)
    session.commit()
    return postulante


@router.post("/postulantes/{postulante_id}/descartar", response_model=schemas.PostulanteOut)
def descartar_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteDescartar,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_postulante(session, postulante_id, tenant)
    postulante = postulantes.descartar_postulante(
        session, postulante_id, motivo=body.motivo
    )
    session.commit()
    return postulante


@router.post("/postulantes/{postulante_id}/contratar", response_model=schemas.PostulanteOut)
def contratar_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteContratar,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cierra la selección creando `persona` + `trabajador`. Exige el permiso
    de trabajador, no el de postulante: acá nace la planilla."""
    exigir_postulante(session, postulante_id, tenant)
    postulante = postulantes.contratar_postulante(
        session, postulante_id, **body.model_dump()
    )
    session.commit()
    return postulante


# --- Socio ---------------------------------------------------------------------
@router.post("/socios", response_model=schemas.SocioOut, status_code=201)
def crear_socio(
    body: schemas.SocioCreate,
    _: Usuario = Depends(require_permission(SOCIO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    # Un socio puede serlo del grupo (`empresa_id` nulo); si se indica
    # empresa, tiene que ser la del usuario.
    if body.empresa_id is not None:
        tenant.exigir_empresa(body.empresa_id)
    socio = socios.crear_socio(session, **body.model_dump())
    session.commit()
    return socio


@router.get("/socios", response_model=list[schemas.SocioOut])
def listar_socios(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return socios.listar_socios(session, tenant.filtro_empresa(empresa_id))


# --- Nómina --------------------------------------------------------------------
@router.post("/boletas-pago", response_model=schemas.BoletaPagoOut, status_code=201)
def emitir_boleta_pago(
    body: schemas.BoletaPagoCreate,
    _: Usuario = Depends(require_permission(NOMINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    boleta = nomina.emitir_boleta_pago(session, **body.model_dump())
    session.commit()
    return boleta


@router.get("/boletas-pago/{boleta_id}", response_model=schemas.BoletaPagoOut)
def ver_boleta_pago(
    boleta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_boleta(session, boleta_id, tenant)


@router.post("/liquidaciones-bss", response_model=schemas.LiquidacionBssOut, status_code=201)
def liquidar_cese(
    body: schemas.LiquidacionBssCreate,
    _: Usuario = Depends(require_permission(NOMINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    liquidacion = nomina.liquidar_cese(session, **body.model_dump())
    session.commit()
    return liquidacion


@router.get("/liquidaciones-bss/{liquidacion_id}", response_model=schemas.LiquidacionBssOut)
def ver_liquidacion_bss(
    liquidacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_liquidacion(session, liquidacion_id, tenant)


# --- Disciplina y documentos -----------------------------------------------------
@router.post("/memorandums", response_model=schemas.MemorandumOut, status_code=201)
def emitir_memorandum(
    body: schemas.MemorandumCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    if campos["destinatario_trabajador_id"] is not None:
        exigir_trabajador(session, campos["destinatario_trabajador_id"], tenant)
    memorandum = disciplina.emitir_memorandum(session, **campos)
    session.commit()
    return memorandum


@router.get("/memorandums/{memorandum_id}", response_model=schemas.MemorandumOut)
def ver_memorandum(
    memorandum_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_memorandum(session, memorandum_id, tenant)


@router.post("/amonestaciones", response_model=schemas.AmonestacionOut, status_code=201)
def emitir_amonestacion(
    body: schemas.AmonestacionCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    amonestacion = disciplina.emitir_amonestacion(session, **body.model_dump())
    session.commit()
    return amonestacion


@router.get("/amonestaciones/{amonestacion_id}", response_model=schemas.AmonestacionOut)
def ver_amonestacion(
    amonestacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_amonestacion(session, amonestacion_id, tenant)


@router.post("/actas", response_model=schemas.ActaOut, status_code=201)
def emitir_acta(
    body: schemas.ActaCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    acta = disciplina.emitir_acta(session, **campos)
    session.commit()
    return acta


@router.get("/actas/{acta_id}", response_model=schemas.ActaOut)
def ver_acta(
    acta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_acta(session, acta_id, tenant)


@router.post(
    "/certificados-trabajo", response_model=schemas.CertificadoTrabajoOut, status_code=201
)
def emitir_certificado_trabajo(
    body: schemas.CertificadoTrabajoCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    certificado = disciplina.emitir_certificado_trabajo(session, **body.model_dump())
    session.commit()
    return certificado


@router.get(
    "/certificados-trabajo/{certificado_id}", response_model=schemas.CertificadoTrabajoOut
)
def ver_certificado_trabajo(
    certificado_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_certificado(session, certificado_id, tenant)


# --- Permisos --------------------------------------------------------------------
@router.post("/solicitudes-permiso", response_model=schemas.SolicitudPermisoOut, status_code=201)
def crear_solicitud_permiso(
    body: schemas.SolicitudPermisoCreate,
    _: Usuario = Depends(require_permission(PERMISO_SOLICITAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    solicitud = permisos.crear_solicitud_permiso(session, **body.model_dump())
    session.commit()
    return solicitud


@router.get("/solicitudes-permiso/{solicitud_id}", response_model=schemas.SolicitudPermisoOut)
def ver_solicitud_permiso(
    solicitud_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_solicitud_permiso(session, solicitud_id, tenant)


@router.post(
    "/solicitudes-permiso/{solicitud_id}/aprobar", response_model=schemas.SolicitudPermisoOut
)
def aprobar_solicitud_permiso(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERMISO_APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud_permiso(session, solicitud_id, tenant)
    solicitud = permisos.aprobar_solicitud_permiso(session, solicitud_id, aprobador_id=actor.id)
    session.commit()
    return solicitud


@router.post(
    "/solicitudes-permiso/{solicitud_id}/rechazar", response_model=schemas.SolicitudPermisoOut
)
def rechazar_solicitud_permiso(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERMISO_APROBAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_solicitud_permiso(session, solicitud_id, tenant)
    solicitud = permisos.rechazar_solicitud_permiso(
        session, solicitud_id, aprobador_id=actor.id
    )
    session.commit()
    return solicitud


# --- Capacitación ------------------------------------------------------------------
@router.post(
    "/pactos-permanencia", response_model=schemas.PactoPermanenciaOut, status_code=201
)
def crear_pacto_permanencia(
    body: schemas.PactoPermanenciaCreate,
    _: Usuario = Depends(require_permission(CAPACITACION_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    pacto = capacitacion.crear_pacto_permanencia(session, **body.model_dump())
    session.commit()
    return pacto


@router.get("/pactos-permanencia/{pacto_id}", response_model=schemas.PactoPermanenciaOut)
def ver_pacto_permanencia(
    pacto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_pacto(session, pacto_id, tenant)


# --- Asistencia --------------------------------------------------------------------
@router.post("/asistencia/entrada", response_model=schemas.AsistenciaOut, status_code=201)
def marcar_entrada(
    body: schemas.AsistenciaMarcarEntrada,
    _: Usuario = Depends(require_permission(ASISTENCIA_MARCAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    asistencia = asistencia_uc.marcar_entrada(session, **body.model_dump())
    session.commit()
    return asistencia


@router.post("/asistencia/salida", response_model=schemas.AsistenciaOut)
def marcar_salida(
    body: schemas.AsistenciaMarcarSalida,
    _: Usuario = Depends(require_permission(ASISTENCIA_MARCAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_trabajador(session, body.trabajador_id, tenant)
    asistencia = asistencia_uc.marcar_salida(session, **body.model_dump())
    session.commit()
    return asistencia


# --- Turno de trabajo ------------------------------------------------------------
@router.post("/turnos", response_model=schemas.TurnoOut, status_code=201)
def crear_turno(
    body: schemas.TurnoCreate,
    _: Usuario = Depends(require_permission(TURNO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    turno = turnos.crear_turno(session, **body.model_dump())
    session.commit()
    return turno


@router.get("/turnos", response_model=list[schemas.TurnoOut])
def listar_turnos(
    sucursal_id: uuid.UUID,
    solo_activos: bool = False,
    _: Usuario = Depends(require_permission(TURNO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(sucursal_id)
    return turnos.listar_turnos(session, sucursal_id, solo_activos)


@router.patch("/turnos/{turno_id}", response_model=schemas.TurnoOut)
def editar_turno(
    turno_id: uuid.UUID,
    body: schemas.TurnoUpdate,
    _: Usuario = Depends(require_permission(TURNO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_turno(session, turno_id, tenant)
    turno = turnos.editar_turno(session, turno_id, **body.model_dump())
    session.commit()
    return turno


# --- Pad de marcación del local --------------------------------------------------
@router.get("/asistencia/terminal/tarjetas", response_model=list[schemas.TarjetaOut])
def tarjetas_del_pad(
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ASISTENCIA_TERMINAL)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Los nombres que se muestran en el pad de esa sucursal, y si ya
    marcaron. Solo el centro de labores del trabajador (ADR-062) decide qué
    tarjeta aparece dónde: el pad de un local no marca por gente de otro."""
    tenant.exigir_sucursal(sucursal_id)
    return pad_asistencia.tarjetas(session, sucursal_id)


@router.post("/asistencia/terminal/marcar", response_model=schemas.PadMarcacionOut)
def marcar_en_el_pad(
    body: schemas.PadMarcarIn,
    request: Request,
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(require_permission(ASISTENCIA_TERMINAL)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Registra la marcación firmada con el PIN del propio trabajador.

    El límite se cuenta **por trabajador** y no por IP: en un local todas
    las tabletas salen por la misma dirección y el cambio de turno son diez
    personas marcando seguido — un límite por IP castigaría a la cola por
    culpa de quien se equivocó de tarjeta.
    """
    tenant.exigir_sucursal(sucursal_id)
    exigir_trabajador(session, body.trabajador_id, tenant)
    if pad_asistencia.sucursal_de(session, body.trabajador_id) != sucursal_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "el trabajador no tiene su centro de labores en esta sucursal",
        )
    consumir("asistencia_pad", str(body.trabajador_id), 10, 300)

    usuario_id = pad_asistencia.usuario_que_firma(session, body.trabajador_id)
    resultado = verificar_pin_de(session, usuario_id, body.pin, ip_de(request))
    if resultado != PIN_OK:
        session.commit()  # persistir el intento fallido y el lockout
        if resultado == PIN_BLOQUEADO:
            raise HTTPException(
                status.HTTP_423_LOCKED, "Usuario bloqueado por intentos fallidos"
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")

    asistencia, tipo = pad_asistencia.marcar(session, trabajador_id=body.trabajador_id)
    auditoria.registrar(
        session,
        usuario_id=usuario_id,
        entidad="asistencia",
        entidad_id=asistencia.id,
        accion=f"marcar_{tipo}",
        ip=ip_de(request),
    )
    session.commit()
    return {"tipo": tipo, "asistencia": asistencia}
