"""Casos de uso de `postulante`: recepción de la postulación (formulario
público o carga manual), avance por el tablero de contratación y paso a
`trabajador` al contratar.

El postulante NO entra a `persona` mientras es candidato: el pool es gente
ajena a la empresa y la mayoría nunca se contrata. `persona` se crea recién
al contratar, fuente única de ahí en adelante (RN-GEN-007).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.modules.rrhh.application import trabajadores
from src.modules.rrhh.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.rrhh.domain import rules
from src.modules.rrhh.infrastructure.models import Postulante
from src.modules.rrhh.infrastructure.repositories import ConvocatoriaRepo, PostulanteRepo
from src.modules.users.infrastructure.models import Empresa, Persona
from src.shared import documento
from src.shared.integrations.factiliza import nombres_desde_dni


def _nuevo_postulante(**campos) -> Postulante:
    if not campos.pop("consentimiento_datos"):
        raise ReglaNegocio(
            "datos de postulante requieren consentimiento previo e informado (RN-PER-004)"
        )
    fecha = campos["fecha_postulacion"]
    campos["consentimiento_fecha"] = campos.get("consentimiento_fecha") or fecha
    # Sin plazo declarado la ficha sería inpurgable y el aviso de privacidad
    # prometería un plazo que nadie aplica: se declara el de la empresa.
    campos["plazo_conservacion_declarado"] = campos.get(
        "plazo_conservacion_declarado"
    ) or rules.sumar_meses(fecha, settings.rrhh_plazo_conservacion_postulante_meses)
    return Postulante(consentimiento_datos=True, **campos)


def crear_postulante(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    nombres: str,
    apellidos: str,
    puesto_postulado: str,
    fecha_postulacion: date,
    consentimiento_datos: bool,
    convocatoria_id: uuid.UUID | None = None,
    telefono: str | None = None,
    email: str | None = None,
    canal_origen: str | None = None,
    respuestas: dict | None = None,
    consentimiento_fecha: date | None = None,
    plazo_conservacion_declarado: date | None = None,
    cv_archivo_id: uuid.UUID | None = None,
) -> Postulante:
    """Carga manual: referido, postulación espontánea o CV que llegó por
    fuera del formulario."""
    if session.get(Empresa, empresa_id) is None:
        raise NoEncontrado(f"empresa {empresa_id} no encontrada")
    if convocatoria_id is not None:
        convocatoria = ConvocatoriaRepo(session).get(convocatoria_id)
        if convocatoria is None:
            raise NoEncontrado("convocatoria no encontrada")
        if convocatoria.empresa_id != empresa_id:
            raise ReglaNegocio("la convocatoria pertenece a otra empresa")

    return PostulanteRepo(session).add(
        _nuevo_postulante(
            empresa_id=empresa_id,
            convocatoria_id=convocatoria_id,
            nombres=nombres,
            apellidos=apellidos,
            telefono=telefono,
            email=email,
            puesto_postulado=puesto_postulado,
            fecha_postulacion=fecha_postulacion,
            canal_origen=canal_origen,
            respuestas=respuestas,
            consentimiento_datos=consentimiento_datos,
            consentimiento_fecha=consentimiento_fecha,
            plazo_conservacion_declarado=plazo_conservacion_declarado,
            cv_archivo_id=cv_archivo_id,
        )
    )


def recibir_postulacion(
    session: Session,
    *,
    token: str,
    nombres: str,
    apellidos: str,
    fecha_postulacion: date,
    consentimiento_datos: bool,
    telefono: str | None = None,
    email: str | None = None,
    canal_origen: str | None = None,
    respuestas: dict | None = None,
) -> Postulante:
    """Entrada del formulario público. El token identifica la convocatoria y
    es lo único que autoriza a escribir — de ahí que solo exista mientras
    está publicada."""
    convocatoria = ConvocatoriaRepo(session).get_por_token(token)
    if convocatoria is None or convocatoria.estado != "publicada":
        raise NoEncontrado("convocatoria no encontrada o cerrada")
    if convocatoria.fecha_limite is not None and fecha_postulacion > convocatoria.fecha_limite:
        raise Conflicto("la convocatoria cerró su fecha límite")

    return PostulanteRepo(session).add(
        _nuevo_postulante(
            empresa_id=convocatoria.empresa_id,
            convocatoria_id=convocatoria.id,
            nombres=nombres,
            apellidos=apellidos,
            telefono=telefono,
            email=email,
            puesto_postulado=convocatoria.puesto,
            fecha_postulacion=fecha_postulacion,
            canal_origen=canal_origen,
            respuestas=respuestas,
            consentimiento_datos=consentimiento_datos,
        )
    )


def listar_postulantes(
    session: Session,
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
    convocatoria_id: uuid.UUID | None = None,
) -> list[Postulante]:
    return PostulanteRepo(session).list(estado, empresa_id, convocatoria_id)


def q_postulantes(
    session: Session,
    estado: str | None = None,
    empresa_id: uuid.UUID | None = None,
    convocatoria_id: uuid.UUID | None = None,
):
    """La consulta sin ejecutar, para que el router la pagine (ADR-026)."""
    return PostulanteRepo(session).q_list(estado, empresa_id, convocatoria_id)


def _cargar(session: Session, postulante_id: uuid.UUID) -> Postulante:
    postulante = PostulanteRepo(session).get(postulante_id)
    if postulante is None or postulante.deleted_at is not None:
        raise NoEncontrado("postulante no encontrado")
    return postulante


def actualizar_postulante(session: Session, postulante_id: uuid.UUID, **campos) -> Postulante:
    """Rectificación (ARCO): corrige los datos de contacto de la ficha."""
    postulante = _cargar(session, postulante_id)
    if postulante.anonimizado_at is not None:
        raise Conflicto("el postulante está anonimizado; no hay dato real que rectificar")
    for campo, valor in campos.items():
        if valor is not None:
            setattr(postulante, campo, valor)
    return postulante


def avanzar_postulante(
    session: Session, postulante_id: uuid.UUID, *, estado: str
) -> Postulante:
    """Mueve la ficha a la columna siguiente del tablero. `contratado` no se
    alcanza por acá: exige crear el trabajador (ver `contratar_postulante`)."""
    postulante = _cargar(session, postulante_id)
    if estado == rules.ETAPA_CONTRATADO:
        raise ReglaNegocio("para contratar use la contratación del postulante")
    if not rules.puede_avanzar_postulante(postulante.estado, estado):
        raise Conflicto(f"no se puede pasar de {postulante.estado} a {estado}")
    postulante.estado = estado
    return postulante


def descartar_postulante(
    session: Session, postulante_id: uuid.UUID, *, motivo: str
) -> Postulante:
    postulante = _cargar(session, postulante_id)
    if not rules.puede_descartar_postulante(postulante.estado):
        raise Conflicto(f"postulante está {postulante.estado}; no admite descarte")
    postulante.estado = rules.ESTADO_DESCARTADO
    postulante.motivo_descarte = motivo
    return postulante


def contratar_postulante(
    session: Session,
    postulante_id: uuid.UUID,
    *,
    cargo: str,
    area: str,
    tipo_vinculo: str,
    fecha_ingreso: date,
    tipo_documento: str | None = None,
    numero_documento: str | None = None,
    # Lo que revisó quien contrata, si corrigió lo que el postulante declaró
    # de sí mismo en el formulario público. Vacío = se usa lo declarado.
    nombres: str | None = None,
    apellidos: str | None = None,
    persona_id: uuid.UUID | None = None,
    regimen_laboral: str | None = None,
    remuneracion_base: Decimal | None = None,
    sistema_pensiones: str | None = None,
    afp_nombre: str | None = None,
    registra_asistencia: bool = True,
    jornada_horas_semana: Decimal | None = None,
    sucursal_id: uuid.UUID | None = None,
) -> Postulante:
    """Cierra la selección: crea la `persona` (o reusa la del ex-trabajador
    recontratado) y su `trabajador`, y deja la ficha en `contratado`."""
    postulante = _cargar(session, postulante_id)
    if not rules.puede_avanzar_postulante(postulante.estado, rules.ETAPA_CONTRATADO):
        raise Conflicto(
            f"postulante está {postulante.estado}; se contrata con la oferta enviada"
        )

    if persona_id is not None:
        persona = session.get(Persona, persona_id)
        if persona is None:
            raise NoEncontrado(f"persona {persona_id} no encontrada")
    else:
        if not numero_documento:
            raise ReglaNegocio("el trabajador exige documento de identidad")
        # El tablero manda `carne_extranjeria`; `persona` lo llama `ce`. La
        # traducción y los largos por tipo viven en `shared.documento`.
        try:
            tipo_documento, numero_documento = documento.validar(
                tipo_documento or documento.DNI, numero_documento
            )
        except ValueError as exc:
            raise ReglaNegocio(str(exc)) from exc
        # El nombre de la planilla lo da RENIEC, no lo que el postulante
        # escribió de sí mismo en el formulario público (RN-PTS-004, mismo
        # criterio que el alta de cliente y de proveedor). Importa acá más
        # que en ningún lado: con ese nombre se firma el contrato y se
        # declara a SUNAT. Si Factiliza no responde o el documento no figura,
        # se usa lo revisado por quien contrata —o lo declarado— y la
        # contratación sigue: nunca se bloquea por un tercero (ADR-005).
        nombres_finales = nombres or postulante.nombres
        apellidos_finales = apellidos or postulante.apellidos
        if tipo_documento == documento.DNI:
            nombres_finales, apellidos_finales = nombres_desde_dni(
                numero_documento, nombres_finales, apellidos_finales
            )
        persona = Persona(
            nombres=nombres_finales,
            apellidos=apellidos_finales,
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            telefono=postulante.telefono,
            email=postulante.email,
        )
        session.add(persona)
        session.flush()

    trabajador = trabajadores.crear_trabajador(
        session,
        empresa_id=postulante.empresa_id,
        persona_id=persona.id,
        cargo=cargo,
        area=area,
        tipo_vinculo=tipo_vinculo,
        fecha_ingreso=fecha_ingreso,
        regimen_laboral=regimen_laboral,
        remuneracion_base=remuneracion_base,
        sistema_pensiones=sistema_pensiones,
        afp_nombre=afp_nombre,
        registra_asistencia=registra_asistencia,
        jornada_horas_semana=jornada_horas_semana,
        sucursal_id=sucursal_id,
    )

    postulante.persona_id = persona.id
    postulante.trabajador_id = trabajador.id
    postulante.estado = rules.ETAPA_CONTRATADO
    return postulante
