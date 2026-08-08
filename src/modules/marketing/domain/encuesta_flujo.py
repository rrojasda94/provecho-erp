"""Recorrido del guion de la encuesta. Puro: sin ORM, sin red.

Trabaja sobre estructuras sueltas (`Nodo`) y no sobre el modelo SQLAlchemy
para que la ramificación —lo único con lógica de verdad acá— se pueda probar
sin base de datos y sin WhatsApp.
"""

from dataclasses import dataclass, field

PUNTAJE_MIN = 1
PUNTAJE_MAX = 5
MAX_LARGO_TEXTO = 500

# Lo que un cliente escribe cuando no quiere contestar el comentario libre.
OMISIONES = ("-", ".", "no", "nada", "ninguno", "ninguna", "skip", "omitir")


@dataclass(frozen=True)
class Nodo:
    codigo: str
    tipo: str
    opciones: tuple[str, ...] = ()
    siguiente_codigo: str | None = None
    saltos: dict[str, str] = field(default_factory=dict)
    obligatoria: bool = True


def valores_aceptados(nodo: Nodo) -> tuple[str, ...]:
    """Respuestas cerradas válidas. Vacío = pregunta abierta."""
    if nodo.tipo == "escala":
        return tuple(str(n) for n in range(PUNTAJE_MIN, PUNTAJE_MAX + 1))
    if nodo.tipo == "si_no":
        return ("si", "no")
    if nodo.tipo == "opcion":
        return nodo.opciones
    return ()


def normalizar(nodo: Nodo, valor: str) -> str:
    """Lo que el cliente tecleó, llevado al valor canónico del nodo.

    Contestar por WhatsApp es escribir, no elegir: llega "Sí", "SI", " 5 " o
    "5 estrellas". Sin esta normalización, media encuesta se rechaza por un
    acento y el cliente abandona.
    """
    limpio = (valor or "").strip()
    if nodo.tipo == "texto":
        return limpio[:MAX_LARGO_TEXTO]
    plano = _sin_tildes(limpio.lower())
    if nodo.tipo == "si_no":
        if plano.startswith("s"):
            return "si"
        if plano.startswith("n"):
            return "no"
        return plano
    if nodo.tipo == "escala":
        digitos = "".join(c for c in plano if c.isdigit())
        return digitos[:1] if digitos else plano
    for opcion in nodo.opciones:
        if plano == _sin_tildes(opcion.lower()):
            return opcion
    return plano


def valor_valido(nodo: Nodo, valor: str) -> bool:
    aceptados = valores_aceptados(nodo)
    if aceptados:
        return valor in aceptados
    if nodo.obligatoria:
        return bool(valor) and valor.lower() not in OMISIONES
    return len(valor) <= MAX_LARGO_TEXTO


def siguiente_codigo(nodo: Nodo, valor: str) -> str | None:
    """A qué nodo sigue la conversación. `None` = la encuesta terminó.

    El salto por respuesta gana al camino normal: es toda la razón de que
    esto sea un guion ramificado y no una lista de preguntas.
    """
    return nodo.saltos.get(valor) or nodo.siguiente_codigo


def puntaje_de(nodo: Nodo, valor: str) -> int | None:
    """El valor como puntaje 1-5, si el nodo es una escala válida."""
    if nodo.tipo != "escala" or not valor.isdigit():
        return None
    puntaje = int(valor)
    return puntaje if PUNTAJE_MIN <= puntaje <= PUNTAJE_MAX else None


def puntaje_valido(puntaje: int) -> bool:
    return PUNTAJE_MIN <= puntaje <= PUNTAJE_MAX


def _sin_tildes(texto: str) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    return texto.translate(tabla)


def plantilla_coherente(nodos: list[Nodo]) -> list[str]:
    """Problemas del guion. Vacío = se puede activar.

    Se valida al guardar y no al enviar: un destino inexistente descubierto a
    mitad de conversación deja al cliente esperando una pregunta que nunca
    llega, y para entonces ya no hay a quién avisarle.
    """
    problemas: list[str] = []
    if not nodos:
        return ["la plantilla no tiene preguntas"]

    codigos = {n.codigo for n in nodos}
    if len(codigos) != len(nodos):
        problemas.append("hay códigos de pregunta repetidos")

    for nodo in nodos:
        destinos = [nodo.siguiente_codigo, *nodo.saltos.values()]
        for destino in destinos:
            if destino is not None and destino not in codigos:
                problemas.append(f"'{nodo.codigo}' apunta a '{destino}', que no existe")
        if nodo.tipo == "opcion" and not nodo.opciones:
            problemas.append(f"'{nodo.codigo}' es de opción y no tiene opciones")
        for valor in nodo.saltos:
            aceptados = valores_aceptados(nodo)
            if aceptados and valor not in aceptados:
                problemas.append(
                    f"'{nodo.codigo}' salta con '{valor}', que no es respuesta suya"
                )

    if not _todos_terminan(nodos):
        problemas.append("hay un ciclo: la encuesta no termina desde la primera pregunta")
    return problemas


def _todos_terminan(nodos: list[Nodo]) -> bool:
    """Recorre el grafo desde el primer nodo y exige que todo camino corte.

    Un ciclo (A → B → A) no rompe nada al guardar y convierte la encuesta en
    un bucle que le escribe al cliente para siempre.
    """
    por_codigo = {n.codigo: n for n in nodos}
    visitando: set[str] = set()
    cerrados: set[str] = set()

    def baja(codigo: str | None) -> bool:
        if codigo is None or codigo not in por_codigo:
            return True
        if codigo in cerrados:
            return True
        if codigo in visitando:
            return False
        visitando.add(codigo)
        nodo = por_codigo[codigo]
        destinos = {nodo.siguiente_codigo, *nodo.saltos.values()}
        resultado = all(baja(d) for d in destinos)
        visitando.discard(codigo)
        cerrados.add(codigo)
        return resultado

    return baja(nodos[0].codigo)
