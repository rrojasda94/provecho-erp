"""Reglas de negocio de marketing. Puras, sin infraestructura."""

CAMPOS_BRIEF = ("objetivo", "publico_objetivo", "presupuesto", "kpi")

PUNTAJE_MIN = 1
PUNTAJE_MAX = 5


def brief_incompleto(campana) -> list[str]:
    """Campos del brief que faltan (RN-MKT-003). Vacío = brief completo."""
    return [c for c in CAMPOS_BRIEF if getattr(campana, c) in (None, "")]


def puede_aprobar(estado: str) -> bool:
    return estado == "brief"


def puede_lanzar(estado: str) -> bool:
    return estado == "aprobada"


def puede_cerrar(estado: str) -> bool:
    return estado in {"aprobada", "en_curso"}


def campana_admite_leads(estado: str) -> bool:
    """Una campaña que no salió a canal no genera leads."""
    return estado == "en_curso"


def puede_publicar(pieza) -> bool:
    """RN-MKT-001/002: contenido no pertinente o con uso de marca sin validar
    no se publica, aunque sea viral."""
    return pieza.pertinente_marca and pieza.uso_marca_validado


def puntaje_valido(puntaje: int) -> bool:
    return PUNTAJE_MIN <= puntaje <= PUNTAJE_MAX
