"""Routers FastAPI del módulo rrhh: ciclo laboral completo."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.modules.rrhh.api import schemas
from src.modules.rrhh.application import (
    asistencia as asistencia_uc,
)
from src.modules.rrhh.application import (
    capacitacion,
    contratos,
    disciplina,
    nomina,
    permisos,
    postulantes,
    socios,
    trabajadores,
)
from src.modules.rrhh.infrastructure.repositories import (
    ActaRepo,
    AmonestacionRepo,
    BoletaPagoRepo,
    CertificadoTrabajoRepo,
    ContratoLaboralRepo,
    LiquidacionBssRepo,
    MemorandumRepo,
    PactoPermanenciaRepo,
    SolicitudPermisoRepo,
    TrabajadorRepo,
)
from src.modules.users.api.deps import get_db, require_permission
from src.modules.users.infrastructure.models import Usuario

router = APIRouter(prefix="/rrhh", tags=["rrhh"])

LEER = "rrhh.leer"
TRABAJADOR_GESTIONAR = "rrhh.trabajador_gestionar"
CONTRATO_GESTIONAR = "rrhh.contrato_gestionar"
POSTULANTE_GESTIONAR = "rrhh.postulante_gestionar"
SOCIO_GESTIONAR = "rrhh.socio_gestionar"
NOMINA_GESTIONAR = "rrhh.nomina_gestionar"
DISCIPLINA_GESTIONAR = "rrhh.disciplina_gestionar"
PERMISO_SOLICITAR = "rrhh.permiso_solicitar"
PERMISO_APROBAR = "rrhh.permiso_aprobar"
ASISTENCIA_MARCAR = "rrhh.asistencia_marcar"
CAPACITACION_GESTIONAR = "rrhh.capacitacion_gestionar"


# --- Trabajador ----------------------------------------------------------------
@router.post("/trabajadores", response_model=schemas.TrabajadorOut, status_code=201)
def crear_trabajador(
    body: schemas.TrabajadorCreate,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    session: Session = Depends(get_db),
):
    trabajador = trabajadores.crear_trabajador(session, **body.model_dump())
    session.commit()
    return trabajador


@router.get("/trabajadores", response_model=list[schemas.TrabajadorOut])
def listar_trabajadores(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return trabajadores.listar_trabajadores(session, empresa_id)


@router.get("/trabajadores/{trabajador_id}", response_model=schemas.TrabajadorOut)
def ver_trabajador(
    trabajador_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    trabajador = TrabajadorRepo(session).get(trabajador_id)
    if trabajador is None:
        raise HTTPException(404, "trabajador no encontrado")
    return trabajador


@router.patch("/trabajadores/{trabajador_id}", response_model=schemas.TrabajadorOut)
def actualizar_trabajador(
    trabajador_id: uuid.UUID,
    body: schemas.TrabajadorUpdate,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    session: Session = Depends(get_db),
):
    trabajador = trabajadores.actualizar_trabajador(session, trabajador_id, **body.model_dump())
    session.commit()
    return trabajador


@router.post("/trabajadores/{trabajador_id}/cesar", response_model=schemas.TrabajadorOut)
def cesar_trabajador(
    trabajador_id: uuid.UUID,
    body: schemas.TrabajadorCese,
    _: Usuario = Depends(require_permission(TRABAJADOR_GESTIONAR)),
    session: Session = Depends(get_db),
):
    trabajador = trabajadores.cesar_trabajador(
        session, trabajador_id, fecha_cese=body.fecha_cese
    )
    session.commit()
    return trabajador


# --- Contrato laboral ------------------------------------------------------------
@router.post("/contratos-laborales", response_model=schemas.ContratoLaboralOut, status_code=201)
def crear_contrato_laboral(
    body: schemas.ContratoLaboralCreate,
    _: Usuario = Depends(require_permission(CONTRATO_GESTIONAR)),
    session: Session = Depends(get_db),
):
    contrato = contratos.crear_contrato_laboral(session, **body.model_dump())
    session.commit()
    return contrato


@router.get("/contratos-laborales/{contrato_id}", response_model=schemas.ContratoLaboralOut)
def ver_contrato_laboral(
    contrato_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    contrato = ContratoLaboralRepo(session).get(contrato_id)
    if contrato is None:
        raise HTTPException(404, "contrato no encontrado")
    return contrato


@router.post(
    "/contratos-laborales/{contrato_id}/firmar", response_model=schemas.ContratoLaboralOut
)


def firmar_contrato_laboral(
    contrato_id: uuid.UUID,
    body: schemas.ContratoLaboralFirmar,
    _: Usuario = Depends(require_permission(CONTRATO_GESTIONAR)),
    session: Session = Depends(get_db),
):
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
    session: Session = Depends(get_db),
):
    contrato = contratos.finalizar_contrato_laboral(session, contrato_id)
    session.commit()
    return contrato


# --- Postulante --------------------------------------------------------------
@router.post("/postulantes", response_model=schemas.PostulanteOut, status_code=201)
def crear_postulante(
    body: schemas.PostulanteCreate,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    session: Session = Depends(get_db),
):
    postulante = postulantes.crear_postulante(session, **body.model_dump())
    session.commit()
    return postulante


@router.get("/postulantes", response_model=list[schemas.PostulanteOut])
def listar_postulantes(
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return postulantes.listar_postulantes(session, estado)


@router.patch("/postulantes/{postulante_id}/estado", response_model=schemas.PostulanteOut)
def cambiar_estado_postulante(
    postulante_id: uuid.UUID,
    body: schemas.PostulanteEstado,
    _: Usuario = Depends(require_permission(POSTULANTE_GESTIONAR)),
    session: Session = Depends(get_db),
):
    postulante = postulantes.cambiar_estado_postulante(
        session, postulante_id, estado=body.estado
    )
    session.commit()
    return postulante


# --- Socio ---------------------------------------------------------------------
@router.post("/socios", response_model=schemas.SocioOut, status_code=201)
def crear_socio(
    body: schemas.SocioCreate,
    _: Usuario = Depends(require_permission(SOCIO_GESTIONAR)),
    session: Session = Depends(get_db),
):
    socio = socios.crear_socio(session, **body.model_dump())
    session.commit()
    return socio


@router.get("/socios", response_model=list[schemas.SocioOut])
def listar_socios(
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return socios.listar_socios(session)


# --- Nómina --------------------------------------------------------------------
@router.post("/boletas-pago", response_model=schemas.BoletaPagoOut, status_code=201)
def emitir_boleta_pago(
    body: schemas.BoletaPagoCreate,
    _: Usuario = Depends(require_permission(NOMINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    boleta = nomina.emitir_boleta_pago(session, **body.model_dump())
    session.commit()
    return boleta


@router.get("/boletas-pago/{boleta_id}", response_model=schemas.BoletaPagoOut)
def ver_boleta_pago(
    boleta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    boleta = BoletaPagoRepo(session).get(boleta_id)
    if boleta is None:
        raise HTTPException(404, "boleta de pago no encontrada")
    return boleta


@router.post("/liquidaciones-bss", response_model=schemas.LiquidacionBssOut, status_code=201)
def liquidar_cese(
    body: schemas.LiquidacionBssCreate,
    _: Usuario = Depends(require_permission(NOMINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    liquidacion = nomina.liquidar_cese(session, **body.model_dump())
    session.commit()
    return liquidacion


@router.get("/liquidaciones-bss/{liquidacion_id}", response_model=schemas.LiquidacionBssOut)
def ver_liquidacion_bss(
    liquidacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    liquidacion = LiquidacionBssRepo(session).get(liquidacion_id)
    if liquidacion is None:
        raise HTTPException(404, "liquidación no encontrada")
    return liquidacion


# --- Disciplina y documentos -----------------------------------------------------
@router.post("/memorandums", response_model=schemas.MemorandumOut, status_code=201)
def emitir_memorandum(
    body: schemas.MemorandumCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    memorandum = disciplina.emitir_memorandum(session, **body.model_dump())
    session.commit()
    return memorandum


@router.get("/memorandums/{memorandum_id}", response_model=schemas.MemorandumOut)
def ver_memorandum(
    memorandum_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    memorandum = MemorandumRepo(session).get(memorandum_id)
    if memorandum is None:
        raise HTTPException(404, "memorándum no encontrado")
    return memorandum


@router.post("/amonestaciones", response_model=schemas.AmonestacionOut, status_code=201)
def emitir_amonestacion(
    body: schemas.AmonestacionCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    amonestacion = disciplina.emitir_amonestacion(session, **body.model_dump())
    session.commit()
    return amonestacion


@router.get("/amonestaciones/{amonestacion_id}", response_model=schemas.AmonestacionOut)
def ver_amonestacion(
    amonestacion_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    amonestacion = AmonestacionRepo(session).get(amonestacion_id)
    if amonestacion is None:
        raise HTTPException(404, "amonestación no encontrada")
    return amonestacion


@router.post("/actas", response_model=schemas.ActaOut, status_code=201)
def emitir_acta(
    body: schemas.ActaCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    acta = disciplina.emitir_acta(session, **body.model_dump())
    session.commit()
    return acta


@router.get("/actas/{acta_id}", response_model=schemas.ActaOut)
def ver_acta(
    acta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    acta = ActaRepo(session).get(acta_id)
    if acta is None:
        raise HTTPException(404, "acta no encontrada")
    return acta


@router.post(
    "/certificados-trabajo", response_model=schemas.CertificadoTrabajoOut, status_code=201
)


def emitir_certificado_trabajo(
    body: schemas.CertificadoTrabajoCreate,
    _: Usuario = Depends(require_permission(DISCIPLINA_GESTIONAR)),
    session: Session = Depends(get_db),
):
    certificado = disciplina.emitir_certificado_trabajo(session, **body.model_dump())
    session.commit()
    return certificado


@router.get(
    "/certificados-trabajo/{certificado_id}", response_model=schemas.CertificadoTrabajoOut
)


def ver_certificado_trabajo(
    certificado_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    certificado = CertificadoTrabajoRepo(session).get(certificado_id)
    if certificado is None:
        raise HTTPException(404, "certificado no encontrado")
    return certificado


# --- Permisos --------------------------------------------------------------------
@router.post("/solicitudes-permiso", response_model=schemas.SolicitudPermisoOut, status_code=201)
def crear_solicitud_permiso(
    body: schemas.SolicitudPermisoCreate,
    _: Usuario = Depends(require_permission(PERMISO_SOLICITAR)),
    session: Session = Depends(get_db),
):
    solicitud = permisos.crear_solicitud_permiso(session, **body.model_dump())
    session.commit()
    return solicitud


@router.get("/solicitudes-permiso/{solicitud_id}", response_model=schemas.SolicitudPermisoOut)
def ver_solicitud_permiso(
    solicitud_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    solicitud = SolicitudPermisoRepo(session).get(solicitud_id)
    if solicitud is None:
        raise HTTPException(404, "solicitud no encontrada")
    return solicitud


@router.post(
    "/solicitudes-permiso/{solicitud_id}/aprobar", response_model=schemas.SolicitudPermisoOut
)


def aprobar_solicitud_permiso(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERMISO_APROBAR)),
    session: Session = Depends(get_db),
):
    solicitud = permisos.aprobar_solicitud_permiso(session, solicitud_id, aprobador_id=actor.id)
    session.commit()
    return solicitud


@router.post(
    "/solicitudes-permiso/{solicitud_id}/rechazar", response_model=schemas.SolicitudPermisoOut
)


def rechazar_solicitud_permiso(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERMISO_APROBAR)),
    session: Session = Depends(get_db),
):
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
    session: Session = Depends(get_db),
):
    pacto = capacitacion.crear_pacto_permanencia(session, **body.model_dump())
    session.commit()
    return pacto


@router.get("/pactos-permanencia/{pacto_id}", response_model=schemas.PactoPermanenciaOut)
def ver_pacto_permanencia(
    pacto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    pacto = PactoPermanenciaRepo(session).get(pacto_id)
    if pacto is None:
        raise HTTPException(404, "pacto de permanencia no encontrado")
    return pacto


# --- Asistencia --------------------------------------------------------------------
@router.post("/asistencia/entrada", response_model=schemas.AsistenciaOut, status_code=201)
def marcar_entrada(
    body: schemas.AsistenciaMarcarEntrada,
    _: Usuario = Depends(require_permission(ASISTENCIA_MARCAR)),
    session: Session = Depends(get_db),
):
    asistencia = asistencia_uc.marcar_entrada(session, **body.model_dump())
    session.commit()
    return asistencia


@router.post("/asistencia/salida", response_model=schemas.AsistenciaOut)
def marcar_salida(
    body: schemas.AsistenciaMarcarSalida,
    _: Usuario = Depends(require_permission(ASISTENCIA_MARCAR)),
    session: Session = Depends(get_db),
):
    asistencia = asistencia_uc.marcar_salida(session, **body.model_dump())
    session.commit()
    return asistencia
