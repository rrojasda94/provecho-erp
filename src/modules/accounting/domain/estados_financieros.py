"""Estructura de los estados financieros: qué rubro del PCGE va en qué línea
del Estado de Situación Financiera y del Estado de Resultados.

**Es una tabla, no configuración.** El mapa rubro→línea sale del PCGE y de la
forma en que el Perú presenta los estados financieros (NIIF, formato SMV); es
el mismo para toda empresa que lleve el plan oficial, así que vive acá y no
en base de datos. Lo que la empresa decide es qué cuentas usa, no en qué
línea del balance aparece la 42.

**Un solo Estado de Resultados, por naturaleza.** Es el que cuadra siempre:
sus líneas cubren todos los rubros de gasto e ingreso del ejercicio, así que
el resultado que arroja es idéntico al que sale de sumar el libro entero. El
estado **por función** (costo de ventas, gastos de venta, de administración)
necesita los asientos de destino del PCGE —elemento 9 contra la 79— que hoy
ningún proceso del ERP genera: presentarlo ahora daría un estado que no cuadra
contra el mayor. Queda anotado como deuda en `ROADMAP.md`.

Coincidencia por **prefijo de código**: la línea declara los prefijos que le
tocan (`("12", "13", "191", "192")`) y una cuenta cae en ella si su código
empieza por alguno. Por eso los prefijos de dos líneas distintas nunca pueden
solaparse — hay una prueba que lo verifica cuenta por cuenta contra el
catálogo del PCGE.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LineaEEFF:
    clave: str
    etiqueta: str
    prefijos: tuple[str, ...]


@dataclass(frozen=True)
class Seccion:
    clave: str
    etiqueta: str
    #: `deudora` suma debe−haber, `acreedora` suma haber−debe. La sección
    #: decide el signo: así una depreciación acumulada (39, saldo acreedor)
    #: resta sola dentro del activo sin necesidad de marcarla como contraria.
    naturaleza: str
    lineas: tuple[LineaEEFF, ...]


# --- Estado de Situación Financiera ------------------------------------------
# El corte corriente/no corriente de las obligaciones financieras (45) y del
# pasivo diferido (49) se toma por rubro. Separar la porción corriente de un
# préstamo exige la fecha de vencimiento de cada cuota, dato que el modelo no
# guarda todavía (deuda en ROADMAP): mientras tanto 45 va entero a no
# corriente, que es lo que corresponde a la mayoría de los préstamos y lo que
# el contador externo reclasifica si hace falta.
ESF: tuple[Seccion, ...] = (
    Seccion(
        "activo_corriente",
        "Activo corriente",
        "deudora",
        (
            LineaEEFF("efectivo", "Efectivo y equivalentes de efectivo", ("10",)),
            LineaEEFF("inversiones_corrientes", "Otros activos financieros", ("11",)),
            LineaEEFF(
                "cuentas_por_cobrar_comerciales",
                "Cuentas por cobrar comerciales (neto)",
                ("12", "13", "191", "192"),
            ),
            LineaEEFF(
                "cuentas_por_cobrar_diversas",
                "Otras cuentas por cobrar (neto)",
                ("14", "16", "17", "193", "194", "195"),
            ),
            LineaEEFF(
                "existencias",
                "Inventarios (neto)",
                ("20", "21", "22", "23", "24", "25", "26", "28", "29"),
            ),
            LineaEEFF(
                "mantenidos_venta", "Activos no corrientes mantenidos para la venta", ("27",)
            ),
            LineaEEFF("anticipados", "Gastos contratados por anticipado", ("18",)),
        ),
    ),
    Seccion(
        "activo_no_corriente",
        "Activo no corriente",
        "deudora",
        (
            LineaEEFF("inversiones", "Inversiones mobiliarias e inmobiliarias", ("30", "31")),
            LineaEEFF(
                "inmuebles",
                "Propiedad, planta y equipo (neto)",
                ("32", "33", "35", "36", "391", "393"),
            ),
            LineaEEFF("intangibles", "Activos intangibles (neto)", ("34", "392")),
            LineaEEFF("activo_diferido", "Activo por impuesto diferido", ("371", "372")),
            LineaEEFF("otros_activos", "Otros activos no corrientes", ("373", "38")),
        ),
    ),
    Seccion(
        "pasivo_corriente",
        "Pasivo corriente",
        "acreedora",
        (
            LineaEEFF("proveedores", "Cuentas por pagar comerciales", ("42", "43")),
            LineaEEFF("tributos", "Tributos y aportes por pagar", ("40",)),
            LineaEEFF("remuneraciones", "Remuneraciones y participaciones por pagar", ("41",)),
            LineaEEFF("otras_por_pagar", "Otras cuentas por pagar", ("44", "46", "47")),
            LineaEEFF("provisiones", "Provisiones", ("48",)),
        ),
    ),
    Seccion(
        "pasivo_no_corriente",
        "Pasivo no corriente",
        "acreedora",
        (
            LineaEEFF("obligaciones_financieras", "Obligaciones financieras", ("45",)),
            LineaEEFF("pasivo_diferido", "Pasivo diferido", ("49",)),
        ),
    ),
    Seccion(
        "patrimonio",
        "Patrimonio neto",
        "acreedora",
        (
            LineaEEFF("capital", "Capital", ("50", "51")),
            LineaEEFF("capital_adicional", "Capital adicional", ("52",)),
            LineaEEFF("reservas", "Reservas", ("58",)),
            LineaEEFF("resultados_no_realizados", "Resultados no realizados", ("56", "57")),
            LineaEEFF("resultados_acumulados", "Resultados acumulados", ("59",)),
        ),
    ),
)

#: Secciones que suman activo, y las que suman pasivo + patrimonio.
SECCIONES_ACTIVO = ("activo_corriente", "activo_no_corriente")
SECCIONES_PASIVO = ("pasivo_corriente", "pasivo_no_corriente")

# --- Estado de Resultados (por naturaleza) -----------------------------------
# Cada bloque cierra con un subtotal acumulado: el resultado corre de arriba
# hacia abajo, igual que en el formato que presenta el contador.
BLOQUES_ER: tuple[tuple[str, str, tuple[Seccion, ...]], ...] = (
    (
        "explotacion",
        "Resultado de explotación",
        (
            Seccion(
                "ingresos_operacionales",
                "Ingresos operacionales",
                "acreedora",
                (
                    LineaEEFF("ventas", "Ventas netas", ("70", "74")),
                    LineaEEFF("otros_ingresos", "Otros ingresos de gestión", ("73", "75", "76")),
                    LineaEEFF(
                        "produccion_almacenada",
                        "Producción almacenada e inmovilizada",
                        ("71", "72"),
                    ),
                ),
            ),
            Seccion(
                "gastos_operacionales",
                "Gastos operacionales",
                "deudora",
                (
                    LineaEEFF("compras", "Compras", ("60",)),
                    LineaEEFF("variacion_existencias", "Variación de existencias", ("61",)),
                    LineaEEFF("costo_ventas", "Costo de ventas", ("69",)),
                    LineaEEFF("personal", "Gastos de personal, directores y gerentes", ("62",)),
                    LineaEEFF("terceros", "Servicios prestados por terceros", ("63",)),
                    LineaEEFF("tributos", "Gastos por tributos", ("64",)),
                    LineaEEFF("otros_gastos", "Otros gastos de gestión", ("65", "66")),
                    LineaEEFF(
                        "depreciacion",
                        "Depreciación, amortización y provisiones",
                        ("68",),
                    ),
                ),
            ),
        ),
    ),
    (
        "antes_de_impuestos",
        "Resultado antes de participaciones e impuesto a la renta",
        (
            Seccion(
                "financieros",
                "Resultado financiero",
                "acreedora",
                (LineaEEFF("ingresos_financieros", "Ingresos financieros", ("77",)),),
            ),
            Seccion(
                "gastos_financieros",
                "Gastos financieros",
                "deudora",
                (LineaEEFF("gastos_financieros", "Gastos financieros", ("67",)),),
            ),
        ),
    ),
    (
        "ejercicio",
        "Resultado del ejercicio",
        (
            Seccion(
                "participaciones_impuestos",
                "Participaciones e impuesto a la renta",
                "deudora",
                (
                    LineaEEFF("participaciones", "Participaciones de los trabajadores", ("87",)),
                    LineaEEFF("impuesto_renta", "Impuesto a la renta", ("88",)),
                ),
            ),
        ),
    ),
)

#: Rubros de resultado que el estado por naturaleza **no** presenta: son la
#: reclasificación por función (elemento 9 contra la 79), que se cancela sola
#: y contarla sería duplicar el gasto.
RUBROS_RECLASIFICACION = ("79", "9")


def es_reclasificacion(codigo: str) -> bool:
    return codigo.startswith("79") or codigo[0] == "9"


def linea_de(codigo: str, secciones: tuple[Seccion, ...]) -> tuple[str, str] | None:
    """`(clave_seccion, clave_linea)` donde cae una cuenta, o `None`.

    El prefijo más largo gana: `191` cae en cuentas por cobrar comerciales
    aunque `19` no esté declarado en ninguna línea.
    """
    mejor: tuple[int, str, str] | None = None
    for seccion in secciones:
        for linea in seccion.lineas:
            for prefijo in linea.prefijos:
                if codigo.startswith(prefijo) and (mejor is None or len(prefijo) > mejor[0]):
                    mejor = (len(prefijo), seccion.clave, linea.clave)
    return None if mejor is None else (mejor[1], mejor[2])
