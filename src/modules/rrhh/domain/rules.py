"""Reglas de negocio de rrhh. Puras, sin infraestructura."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

TIPOS_VINCULO = {"planilla", "practicante", "locacion_servicios"}
ESTADOS_TRABAJADOR = {"activo", "cesado", "suspendido"}
MODALIDADES_CONTRATO = {
    "indeterminado",
    "modal_inicio_incremento",
    "modal_necesidad_mercado",
    "modal_temporada",
    "tiempo_parcial",
    "jornada_reducida",
}
TIPOS_SOLICITUD_PERMISO = {
    "vacaciones",
    "licencia_con_goce",
    "licencia_sin_goce",
    "permiso_horas",
}
JORNADA_MAXIMA_PRACTICANTE_HORAS = Decimal("6")

MOTIVOS_CONVOCATORIA = ("reemplazo", "refuerzo", "puesto_nuevo")
ESTADOS_CONVOCATORIA = ("borrador", "publicada", "cerrada")

# Columnas del tablero de contratación, en orden: de la postulación recibida
# al fin del periodo de prueba. Es UN solo tablero para los 13 pasos de
# `docs/rrhh/README.md` — el postulante es el expediente de la búsqueda y se
# cierra cuando la persona queda confirmada, no cuando firma.
ETAPAS_POSTULANTE = (
    "recibido",
    "preseleccionado",
    "entrevistado",
    "verificado",
    "oferta_enviada",
    "contratado",
    "inducido",
    "confirmado",
)
ETAPA_CONTRATADO = "contratado"
ESTADO_DESCARTADO = "descartado"
ESTADOS_POSTULANTE = (*ETAPAS_POSTULANTE, ESTADO_DESCARTADO)


def puede_cesar_trabajador(estado: str) -> bool:
    return estado in ("activo", "suspendido")


def valida_registra_asistencia(tipo_vinculo: str, registra_asistencia: bool) -> bool:
    """RN-PER-002: locación de servicios nunca registra asistencia — marcarla
    es evidencia de subordinación y expone a la empresa a vínculo laboral
    retroactivo declarado por SUNAFIL."""
    if tipo_vinculo == "locacion_servicios":
        return not registra_asistencia
    return True


def valida_subvencion_practicante(
    remuneracion: Decimal, jornada_horas_semana: Decimal, rmv: Decimal
) -> bool:
    """RN-PER-001: subvención no menor a 1 RMV cuando la jornada es la
    máxima permitida (30h/semana)."""
    if jornada_horas_semana >= JORNADA_MAXIMA_PRACTICANTE_HORAS * 5:
        return remuneracion >= rmv
    return True


def puede_firmar_contrato(estado: str) -> bool:
    return estado == "borrador"


def puede_finalizar_contrato(estado: str) -> bool:
    return estado == "firmado"


def puede_resolver_solicitud_permiso(estado: str) -> bool:
    return estado == "pendiente"


def puede_publicar_convocatoria(estado: str, perfil_puesto: str | None) -> bool:
    """RN-RRHH-013: ninguna convocatoria se publica sin perfil de puesto
    aprobado."""
    return estado == "borrador" and bool(perfil_puesto)


def puede_avanzar_postulante(actual: str, destino: str) -> bool:
    """Solo se avanza a la columna siguiente del tablero.

    ponytail: sin saltos ni retrocesos — el historial del proceso de selección
    es la defensa ante un reclamo, y un salto lo vuelve inexplicable. Si un
    arrastre mal soltado se vuelve un dolor real, agregar corrección con
    permiso propio y motivo.
    """
    if actual not in ETAPAS_POSTULANTE or destino not in ETAPAS_POSTULANTE:
        return False
    return ETAPAS_POSTULANTE.index(destino) == ETAPAS_POSTULANTE.index(actual) + 1


def puede_descartar_postulante(estado: str) -> bool:
    """Se descarta en cualquier momento del proceso de selección. Ya
    contratado, la salida es un cese (RN-RRHH-012), no un descarte."""
    return estado in ETAPAS_POSTULANTE[: ETAPAS_POSTULANTE.index(ETAPA_CONTRATADO)]


def calcular_reembolso_pacto(
    costo_financiado: Decimal, plazo_meses: int, meses_cumplidos: int
) -> Decimal:
    """RN-RRHH-006: reembolso proporcional al tiempo de permanencia NO
    cumplido."""
    if plazo_meses <= 0:
        raise ValueError("plazo_meses debe ser > 0")
    meses_incumplidos = max(plazo_meses - meses_cumplidos, 0)
    return (costo_financiado * meses_incumplidos / plazo_meses).quantize(Decimal("0.01"))


def dentro_de_plazo_horas(fecha_evento: date, fecha_emision: date, horas: int = 48) -> bool:
    """RN-RRHH-002/003: certificado de trabajo y liquidación de beneficios
    sociales se emiten dentro de 48 h del cese."""
    return (fecha_emision - fecha_evento) <= timedelta(hours=horas)


def sumar_meses(desde: date, meses: int) -> date:
    """Suma calendario, no 30 días: el 31 de enero + 1 mes es el 28/29 de
    febrero, no el 2 de marzo."""
    indice = desde.month - 1 + meses
    anio = desde.year + indice // 12
    mes = indice % 12 + 1
    return date(anio, mes, min(desde.day, calendar.monthrange(anio, mes)[1]))


def meses_servicio(fecha_ingreso: date, fecha_cese: date) -> int:
    return (fecha_cese.year - fecha_ingreso.year) * 12 + (fecha_cese.month - fecha_ingreso.month)
