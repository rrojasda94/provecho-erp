"""Modelos del módulo rrhh: ciclo laboral completo (data-model.md §8b)."""

from src.modules.rrhh.infrastructure.models.acta import Acta
from src.modules.rrhh.infrastructure.models.amonestacion import Amonestacion
from src.modules.rrhh.infrastructure.models.asistencia import Asistencia
from src.modules.rrhh.infrastructure.models.boleta_pago import BoletaPago
from src.modules.rrhh.infrastructure.models.certificado_trabajo import CertificadoTrabajo
from src.modules.rrhh.infrastructure.models.contrato_laboral import ContratoLaboral
from src.modules.rrhh.infrastructure.models.convocatoria import Convocatoria
from src.modules.rrhh.infrastructure.models.liquidacion_bss import LiquidacionBss
from src.modules.rrhh.infrastructure.models.memorandum import Memorandum
from src.modules.rrhh.infrastructure.models.pacto_permanencia import PactoPermanencia
from src.modules.rrhh.infrastructure.models.postulante import Postulante
from src.modules.rrhh.infrastructure.models.socio import Socio
from src.modules.rrhh.infrastructure.models.solicitud_permiso import SolicitudPermiso
from src.modules.rrhh.infrastructure.models.trabajador import Trabajador
from src.modules.rrhh.infrastructure.models.turno_sucursal import TurnoSucursal

__all__ = [
    "Acta",
    "Amonestacion",
    "Asistencia",
    "BoletaPago",
    "CertificadoTrabajo",
    "ContratoLaboral",
    "Convocatoria",
    "LiquidacionBss",
    "Memorandum",
    "PactoPermanencia",
    "Postulante",
    "Socio",
    "SolicitudPermiso",
    "Trabajador",
    "TurnoSucursal",
]
