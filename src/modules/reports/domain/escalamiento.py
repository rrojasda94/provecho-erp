"""Reglas de la cadena de escalamiento (RN-CTP-004, ADR-036).

Dominio puro: sin ORM, sin FastAPI, sin red (`tests/test_arquitectura.py` lo
exige). Acá vive lo que se puede decidir mirando solo el estado del
escalamiento y el reporte que lo originó.
"""

ORIGENES = ("central_pedidos", "punto_venta", "produccion")

MOTIVOS = (
    "queja",
    "demora",
    "error_sistema",
    "desistimiento_no_resuelto",
    "no_conformidad_calidad",
)

# En orden. La cadena sube de a un escalón: saltar de supervisor a gerencia
# deja sin registro el nivel que no intentó resolverlo (RN-REP-012).
NIVELES = ("supervisor", "comercial", "gerencia")

ESTADOS = ("abierto", "resuelto_supervisor", "escalado", "resuelto", "cerrado")

# Un escalamiento terminado no se eleva ni se vuelve a accionar, y libera el
# reporte para una cadena nueva si el problema reaparece. Los tres son los que
# el CHECK de la tabla obliga a fechar con `cerrado_at`.
ESTADOS_TERMINADOS = ("resuelto_supervisor", "resuelto", "cerrado")

# El estado con el que queda al resolver, según dónde se resolvió. Que el
# supervisor tenga su propio estado no es cosmético: separa "se resolvió donde
# tenía que resolverse" de "hubo que subirlo", que es el número que mira la
# mejora continua.
ESTADO_AL_RESOLVER = {
    "supervisor": "resuelto_supervisor",
    "comercial": "resuelto",
    "gerencia": "resuelto",
}


def siguiente_nivel(nivel: str) -> str | None:
    """El escalón de arriba, o `None` si ya está en el último."""
    if nivel not in NIVELES:
        return None
    i = NIVELES.index(nivel)
    return NIVELES[i + 1] if i + 1 < len(NIVELES) else None


def puede_elevar(estado: str, nivel: str) -> bool:
    return estado not in ESTADOS_TERMINADOS and siguiente_nivel(nivel) is not None


def puede_accionar(estado: str) -> bool:
    return estado not in ESTADOS_TERMINADOS


def origen_de(referencia_tipo: str | None, sucursal_id, codigo_emision: str) -> str:
    """De dónde nace el escalamiento, derivado del reporte que lo originó.

    Se deriva y no se pide: el que eleva ya dijo qué reporte está elevando, y
    hacerle elegir el origen es pedirle que repita un dato que el ERP tiene —
    con la chance de que lo repita mal.
    """
    if referencia_tipo == "orden_produccion":
        return "produccion"
    if sucursal_id is not None:
        return "punto_venta"
    if codigo_emision.startswith("sales."):
        return "central_pedidos"
    return "punto_venta"


def exige_evidencia(motivo: str, resultado: str | None) -> bool:
    """RN-PRD-015: una no conformidad que termina en desecho necesita foto.

    `resultado` sale de la foto `datos` del reporte de origen; que sea `None`
    significa que el reporte no lo declaró, no que no hubo desecho — pero sin
    el dato no se puede exigir prueba de algo que no consta.
    """
    return motivo == "no_conformidad_calidad" and resultado == "no_conforme_desechado"
