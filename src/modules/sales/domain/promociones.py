"""Motor de promociones condicionales (ADR-076).

Reglas puras: entra lo que el pedido lleva, sale cuánto se descuenta y por
qué. Sin sesión, sin ORM y sin fecha del sistema — todo lo que decide entra
por parámetro, que es lo que permite probar "el martes a las 20:00 con dos
pizzas" sin montar una venta.

**Nada de acá escribe en `venta.descuento_*`.** Esos campos son el descuento
manual: un acto humano con motivo y autorizador. Mezclar los dos haría
imposible que el reporte distinga lo que regaló un supervisor de lo que
aplicó una regla, que es justamente el dato por el que existe (RN-COM-017).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

TIPOS = {"nxm", "cantidad", "combo", "monto_minimo"}

CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class LineaPromocionable:
    """Una línea del pedido, con lo poco que una promoción necesita saber.

    Se pasa el `precio_unitario` **sin extras**: una promoción sobre "la
    segunda pizza" no puede regalar los agregados que el cliente pidió
    aparte, y el extra es una línea propia (RN-COM-021) que llega acá por su
    cuenta o no llega.
    """

    venta_item_id: str
    producto_id: str
    categoria_id: str | None
    cantidad: int
    precio_unitario: Decimal


@dataclass(frozen=True)
class Regla:
    """Una promoción, ya despojada de todo lo que no decide el cálculo."""

    id: str
    nombre: str
    tipo: str
    condicion: dict
    beneficio: dict
    prioridad: int = 0
    acumulable: bool = False


@dataclass(frozen=True)
class Aplicacion:
    """Lo que una regla descontó, y sobre qué."""

    regla_id: str
    nombre: str
    monto: Decimal
    # `venta_item_id` → unidades que esta promoción consumió. Es lo que
    # impide que dos reglas cobren la misma pizza (ver `aplicar`).
    consumo: dict[str, int]


def vigente(
    *,
    desde: date | None,
    hasta: date | None,
    dias_semana: list[int] | None,
    hora_desde: time | None,
    hora_hasta: time | None,
    dia: date,
    hora: time,
) -> bool:
    """¿La promoción corre en este momento del negocio?

    La franja horaria admite cruzar la medianoche (`22:00`–`02:00`): un
    happy hour de madrugada es un caso real, y compararla como un rango
    simple lo dejaría siempre fuera.
    """
    if desde is not None and dia < desde:
        return False
    if hasta is not None and dia > hasta:
        return False
    if dias_semana and dia.weekday() not in dias_semana:
        return False
    if hora_desde is None or hora_hasta is None:
        return True
    if hora_desde <= hora_hasta:
        return hora_desde <= hora <= hora_hasta
    return hora >= hora_desde or hora <= hora_hasta


def _alcanza(linea: LineaPromocionable, condicion: dict) -> bool:
    """¿Esta línea es de las que la condición mira?

    Sin productos ni categorías declaradas, **todas**: una promoción de
    monto mínimo aplica al pedido entero, y obligar a enumerar la carta para
    decir "todo" sería una lista que se desactualiza sola.
    """
    productos = condicion.get("producto_ids") or []
    categorias = condicion.get("categoria_ids") or []
    if not productos and not categorias:
        return True
    return linea.producto_id in productos or (
        linea.categoria_id is not None and linea.categoria_id in categorias
    )


def _unidades(
    lineas: list[LineaPromocionable], condicion: dict, ya_usadas: Counter
) -> list[tuple[LineaPromocionable, Decimal]]:
    """Las unidades sueltas que la condición alcanza y nadie consumió, de la
    más barata a la más cara.

    Se explota la cantidad en unidades porque las promociones cuentan
    unidades, no líneas: "la segunda pizza" con una sola línea de cantidad 2
    tiene que activarse igual.

    Ordenadas por precio ascendente **a propósito**: lo que se libera es
    siempre lo más barato del conjunto. Al revés, un 2x1 entre una pizza
    familiar y una personal regalaría la familiar, que no es lo que ninguna
    promoción del rubro promete.
    """
    sueltas: list[tuple[LineaPromocionable, Decimal]] = []
    for linea in lineas:
        if not _alcanza(linea, condicion):
            continue
        disponibles = linea.cantidad - ya_usadas[linea.venta_item_id]
        sueltas.extend((linea, linea.precio_unitario) for _ in range(max(0, disponibles)))
    return sorted(sueltas, key=lambda par: par[1])


def _redondear(monto: Decimal) -> Decimal:
    return max(Decimal(0), monto).quantize(CENTAVO)


def _nxm(regla: Regla, lineas, ya_usadas) -> Aplicacion | None:
    """Lleva N, y M de ellas van con descuento.

    Cubre 2x1 (`lleva=2, libera=1, pct=100`), 3x2 y "la segunda a mitad de
    precio" (`pct=50`): el beneficio es un porcentaje sobre las unidades
    liberadas, no un booleano de "gratis". Sin eso, la promoción más común
    del rubro necesitaría su propio tipo.

    Se repite mientras el pedido alcance para otro grupo: seis pizzas con un
    2x1 son tres regaladas, no una.
    """
    lleva = int(regla.condicion.get("lleva") or 0)
    libera = int(regla.beneficio.get("libera") or 0)
    pct = Decimal(str(regla.beneficio.get("descuento_pct") or 100))
    if lleva <= 0 or libera <= 0 or libera >= lleva:
        return None

    sueltas = _unidades(lineas, regla.condicion, ya_usadas)
    grupos = len(sueltas) // lleva
    if grupos == 0:
        return None

    monto = Decimal(0)
    consumo: Counter = Counter()
    for i in range(grupos):
        grupo = sueltas[i * lleva : (i + 1) * lleva]
        # Las liberadas son las más baratas del grupo, y el grupo ya viene
        # ordenado por precio.
        for _, precio in grupo[:libera]:
            monto += precio * pct / Decimal(100)
        for linea, _ in grupo:
            consumo[linea.venta_item_id] += 1
    return Aplicacion(regla.id, regla.nombre, _redondear(monto), dict(consumo))


def _cantidad(regla: Regla, lineas, ya_usadas) -> Aplicacion | None:
    """Desde X unidades de un producto o categoría, % o monto sobre esas
    líneas. "Si te llevas 6 gaseosas, 15% en las gaseosas."
    """
    minimo = int(regla.condicion.get("minimo") or 0)
    if minimo <= 0:
        return None
    sueltas = _unidades(lineas, regla.condicion, ya_usadas)
    if len(sueltas) < minimo:
        return None

    base = sum((precio for _, precio in sueltas), Decimal(0))
    monto = _beneficio_sobre(regla.beneficio, base)
    if monto <= 0:
        return None
    consumo: Counter = Counter()
    for linea, _ in sueltas:
        consumo[linea.venta_item_id] += 1
    return Aplicacion(regla.id, regla.nombre, _redondear(monto), dict(consumo))


def _combo(regla: Regla, lineas, ya_usadas) -> Aplicacion | None:
    """Lleva **todos** estos productos y el conjunto baja a un precio fijo,
    o uno de ellos sale gratis.

    Distinto de `cantidad`, que mira un conjunto y cuenta: acá cada producto
    de la lista tiene que estar. Es la diferencia entre "6 gaseosas" y
    "hamburguesa + papas + gaseosa".
    """
    requeridos = list(regla.condicion.get("producto_ids") or [])
    if not requeridos:
        return None

    elegidas: list[LineaPromocionable] = []
    consumo: Counter = Counter()
    for producto_id in requeridos:
        candidata = next(
            (
                linea
                for linea in lineas
                if linea.producto_id == producto_id
                and linea.cantidad - ya_usadas[linea.venta_item_id]
                - consumo[linea.venta_item_id]
                > 0
            ),
            None,
        )
        if candidata is None:
            return None
        elegidas.append(candidata)
        consumo[candidata.venta_item_id] += 1

    base = sum((linea.precio_unitario for linea in elegidas), Decimal(0))
    gratis = regla.beneficio.get("gratis_producto_id")
    if gratis:
        monto = next(
            (linea.precio_unitario for linea in elegidas if linea.producto_id == gratis),
            Decimal(0),
        )
    elif regla.beneficio.get("precio_fijo") is not None:
        monto = base - Decimal(str(regla.beneficio["precio_fijo"]))
    else:
        monto = _beneficio_sobre(regla.beneficio, base)
    if monto <= 0:
        return None
    return Aplicacion(regla.id, regla.nombre, _redondear(monto), dict(consumo))


def _monto_minimo(regla: Regla, lineas, ya_usadas) -> Aplicacion | None:
    """Desde S/ X de pedido, % o monto sobre el total de productos.

    Con `minimo=0` es "siempre que esté vigente", que es como se expresa un
    precio de franja horaria: el martes de pizzas no pone condiciones sobre
    lo que el cliente lleva, solo sobre cuándo lo lleva.
    """
    minimo = Decimal(str(regla.condicion.get("minimo") or 0))
    sueltas = _unidades(lineas, regla.condicion, ya_usadas)
    base = sum((precio for _, precio in sueltas), Decimal(0))
    if base < minimo or base <= 0:
        return None
    monto = _beneficio_sobre(regla.beneficio, base)
    if monto <= 0:
        return None
    consumo: Counter = Counter()
    for linea, _ in sueltas:
        consumo[linea.venta_item_id] += 1
    return Aplicacion(regla.id, regla.nombre, _redondear(min(monto, base)), dict(consumo))


def _beneficio_sobre(beneficio: dict, base: Decimal) -> Decimal:
    """Un beneficio se declara en porcentaje **o** en monto, nunca en los
    dos: el porcentaje gana si vienen ambos, para que el dato incoherente no
    dependa del orden en que se lea."""
    if beneficio.get("descuento_pct") is not None:
        return base * Decimal(str(beneficio["descuento_pct"])) / Decimal(100)
    if beneficio.get("descuento_monto") is not None:
        return min(Decimal(str(beneficio["descuento_monto"])), base)
    return Decimal(0)


_MOTORES = {
    "nxm": _nxm,
    "cantidad": _cantidad,
    "combo": _combo,
    "monto_minimo": _monto_minimo,
}


def aplicar(
    reglas: list[Regla], lineas: list[LineaPromocionable]
) -> list[Aplicacion]:
    """Qué promociones activa este pedido y cuánto descuenta cada una.

    **Cada unidad la consume una sola promoción**, salvo las marcadas
    `acumulable`. Sin eso, un 2x1 y un "20 % en pizzas" se cobrarían los dos
    sobre la misma pizza y el local terminaría regalando más de lo que
    aprobó. Se recorre por `prioridad` descendente: la regla que el negocio
    considera más importante toma sus unidades primero.

    Una `acumulable` **ignora lo que otras consumieron y no consume nada**:
    se suma encima, que es lo que la palabra dice. Las dos mitades importan —
    si mirara lo consumido, el orden de prioridad decidiría si se aplica o
    no; y si consumiera, un "10 % sobre todo el pedido" impediría que el 2x1
    se activara después. Es el único caso en que dos promociones tocan la
    misma unidad, y por eso el default es `False`.
    """
    ordenadas = sorted(reglas, key=lambda r: (-r.prioridad, r.nombre))
    usadas: Counter = Counter()
    aplicaciones: list[Aplicacion] = []
    for regla in ordenadas:
        motor = _MOTORES.get(regla.tipo)
        if motor is None:
            continue
        resultado = motor(regla, lineas, Counter() if regla.acumulable else usadas)
        if resultado is None or resultado.monto <= 0:
            continue
        aplicaciones.append(resultado)
        if not regla.acumulable:
            usadas.update(resultado.consumo)
    return aplicaciones


def total_promociones(aplicaciones: list[Aplicacion]) -> Decimal:
    return sum((a.monto for a in aplicaciones), Decimal(0))
