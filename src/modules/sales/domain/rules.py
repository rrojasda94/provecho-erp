"""Reglas de negocio de venta y cobro. Puras, sin infraestructura."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

CANALES = {"pdv", "agente_ia", "delivery"}
MODALIDADES = {"mesa", "takeout", "delivery"}

# --- Tipo de venta (RN-COM-025) ----------------------------------------------
# La comida que el negocio le da a su personal se prepara y despacha como
# cualquier pedido, pero no es una venta: no tiene precio, no se cobra y no
# emite comprobante. Su costo es gasto de alimentación de personal, no
# ingreso; por eso viaja tipada y no como una venta con 100% de descuento.
TIPOS_VENTA = {"venta", "consumo_personal"}
MOTIVOS_CONSUMO_PERSONAL = {
    "fin_semana",
    "feriado",
    "alta_actividad",
    "capacitacion",
    "otro",
}


def es_consumo_personal(tipo: str | None) -> bool:
    return tipo == "consumo_personal"


def admite_cobro(tipo: str | None) -> bool:
    """Solo una venta se cobra. Un consumo de personal vale cero: dejarlo
    entrar al cobro lo mandaría a emitir un comprobante de S/ 0.00."""
    return not es_consumo_personal(tipo)


def especificidad_lista(sucursal_id, canal: str | None, modalidad: str | None) -> int:
    """Cuántas dimensiones de ámbito acota una lista de precios. Una lista de
    sucursal+canal (2) gana a una de solo canal (1)."""
    return sum(1 for campo in (sucursal_id, canal, modalidad) if campo is not None)


def elegir_lista_precio(candidatas: list) -> object | None:
    """De las listas ya filtradas por vigencia y ámbito compatible, gana la
    promocional; a igualdad, la más específica; luego la de vigencia más
    reciente (RN-PRC-003/005). Al vencer la promoción el precio regular
    vuelve solo: nada que revertir a mano."""
    return max(
        candidatas,
        key=lambda lp: (
            lp.es_promocional,
            especificidad_lista(lp.sucursal_id, lp.canal, lp.modalidad),
            lp.vigente_desde,
        ),
        default=None,
    )


def total_venta(items: list[tuple[Decimal, Decimal, Decimal]]) -> Decimal:
    """items = [(cantidad, precio_unitario, descuento)]."""
    return sum(
        (cant * precio - desc for cant, precio, desc in items), Decimal(0)
    )


#: Cuánto dura la corrección de lo recién enviado a cocina (RN-COM-029).
#:
#: Dentro de esta ventana, quitar una línea o anular la orden es corregir un
#: error de tecleo: la comanda acaba de salir, el plato todavía no se armó y
#: nadie tuvo tiempo de aprovecharlo. Pasada la ventana el insumo ya se usó de
#: verdad, y ahí sí hace falta que un supervisor firme.
#:
#: Cinco minutos porque es lo que dura un error honesto en caja: más corto y
#: el cajero termina llamando al encargado por cada dedo mal puesto, más largo
#: y deja de ser corrección.
VENTANA_CORRECCION = timedelta(minutes=5)


def dentro_de_ventana(momento: datetime, ahora: datetime | None = None) -> bool:
    """¿`momento` cae dentro de la ventana de corrección?

    Compara en naive UTC: las columnas `created_at` de SQLite vuelven sin
    tzinfo y restarle un `datetime` con zona revienta. Un `momento` que ya
    trae zona se normaliza; uno sin zona se asume UTC, que es lo que el
    servidor escribe.
    """
    ahora = ahora or datetime.now(UTC)
    return _sin_zona(ahora) - _sin_zona(momento) <= VENTANA_CORRECCION


def _sin_zona(valor: datetime) -> datetime:
    return valor.replace(tzinfo=None) if valor.tzinfo else valor


def pagos_cubren_total(pagos_confirmados: list[Decimal], total: Decimal) -> bool:
    """La venta pasa a `pagada` cuando los pagos confirmados igualan el
    total (RN-COM-016). No se admite sobrepago."""
    return sum(pagos_confirmados, Decimal(0)) == total


# --- Descuento manual de la orden (RN-COM-017) -------------------------------
MODOS_DESCUENTO = {"porcentaje", "monto"}
# Un descuento sin motivo no es auditable: el reporte necesita saber por qué
# se regaló margen, no solo cuánto.
# `cupon` es el único motivo que NO nace de la discreción de un supervisor:
# lo trae el cliente y el cajero solo lo teclea (ADR-061). Está en el mismo
# conjunto para que `venta.total` siga siendo uno solo, y separado como
# motivo para que el reporte de descuentos pueda distinguir el margen que se
# regaló a criterio del que se había prometido en una campaña.
MOTIVOS_DESCUENTO = {
    "cortesia",
    "reclamo",
    "colaborador",
    "promocion",
    "convenio",
    "cupon",
}
MOTIVO_CUPON = "cupon"


def monto_descuento(
    modo: str | None, valor: Decimal | None, base: Decimal
) -> Decimal:
    """Cuánto descuenta la orden sobre `base`. Nunca supera la base: un
    descuento del 120% no deja la venta en negativo."""
    if modo is None or valor is None or base <= 0:
        return Decimal(0)
    bruto = base * valor / Decimal(100) if modo == "porcentaje" else valor
    return min(max(bruto, Decimal(0)), base).quantize(Decimal("0.01"))


def repartir_descuento(
    descuento: Decimal, subtotales: list[Decimal]
) -> list[Decimal]:
    """Baja el descuento de la orden a las líneas, a prorrata de cada una.

    El comprobante electrónico no acepta un descuento global: hay que
    llevarlo al precio unitario. El residuo de redondeo va a la línea más
    grande para que la suma cuadre al céntimo con el total cobrado.
    """
    base = sum(subtotales, Decimal(0))
    if descuento <= 0 or base <= 0:
        return [Decimal(0) for _ in subtotales]
    partes = [
        (descuento * sub / base).quantize(Decimal("0.01")) for sub in subtotales
    ]
    residuo = descuento - sum(partes, Decimal(0))
    if residuo:
        mayor = subtotales.index(max(subtotales))
        partes[mayor] += residuo
    return partes


def descuento_prorrateado(
    modo: str | None, valor: Decimal | None, base: Decimal, parcial: Decimal
) -> Decimal:
    """Reparte el descuento de la orden entre los grupos de cobro según lo
    que pesa cada uno: cobrar media cuenta descuenta la mitad. Sin prorrateo,
    el primer grupo en cobrarse se llevaría todo el beneficio."""
    if base <= 0:
        return Decimal(0)
    total = monto_descuento(modo, valor, base)
    return (total * parcial / base).quantize(Decimal("0.01"))


# --- Cobro por grupos (RN-COM-018) -------------------------------------------
GRUPO_COBRO_UNICO = 1


def grupos_de_cobro(grupos_items: list[int]) -> list[int]:
    """Los grupos realmente presentes en la venta, en orden. Una venta sin
    dividir devuelve `[1]`."""
    return sorted(set(grupos_items)) or [GRUPO_COBRO_UNICO]


def venta_totalmente_pagada(saldos_por_grupo: list[Decimal]) -> bool:
    """La venta pasa a `pagada` recién cuando NINGÚN grupo queda con saldo.
    Cobrar una cuenta de tres no cierra la venta."""
    return bool(saldos_por_grupo) and all(s <= 0 for s in saldos_por_grupo)


def puede_anular(estado: str) -> bool:
    """Solo una orden aún no pagada se anula por esta vía; anulación
    post-pago = nota de crédito (`comprobantes.emitir_nota_credito`)."""
    return estado == "orden"


# --- Nota de crédito (RN-CPP-009) --------------------------------------------
def puede_notacreditar(estado_emision: str, ya_anulado: bool) -> bool:
    """Solo se acredita lo que SUNAT aceptó, y una sola vez.

    Un comprobante `pendiente` o `rechazado` no existe para SUNAT: si está
    mal, se corrige antes de emitirlo. Y un documento ya anulado por una NC
    total no admite otra — acreditar dos veces la misma venta la duplicaría
    en negativo.
    """
    return estado_emision == "aceptado" and not ya_anulado


def cantidades_acreditables(
    devueltas: dict, vendidas: dict, ya_acreditadas: dict
) -> list[str]:
    """Errores de un detalle de NC parcial contra lo que queda por acreditar.

    Devuelve la lista de problemas (vacía = detalle válido). Acreditar más
    de lo vendido convierte una devolución en una nota de crédito inventada,
    y sumada a NC anteriores del mismo comprobante es la forma fácil de
    devolver dos veces el mismo plato.
    """
    problemas = []
    for item_id, cantidad in devueltas.items():
        if cantidad <= 0:
            problemas.append(f"la línea {item_id} devuelve una cantidad no positiva")
            continue
        vendida = vendidas.get(item_id)
        if vendida is None:
            problemas.append(f"la línea {item_id} no pertenece a este comprobante")
            continue
        disponible = vendida - ya_acreditadas.get(item_id, 0)
        if cantidad > disponible:
            problemas.append(
                f"la línea {item_id} devuelve {cantidad} y solo quedan {disponible}"
            )
    return problemas


def precio_unitario_neto(
    cantidad: Decimal, precio_unitario: Decimal, descuento: Decimal
) -> Decimal:
    """Precio por unidad ya descontado. El descuento de `venta_item` es un
    monto sobre la línea completa; el comprobante electrónico lo necesita
    repartido por unidad."""
    if cantidad <= 0:
        return precio_unitario
    return precio_unitario - (descuento / cantidad)


# --- Comprobante electrónico -------------------------------------------------
# Catálogo 06 de SUNAT (tipo de documento de identidad).
DOC_SUNAT_SIN_DOCUMENTO = "0"
DOC_SUNAT_DNI = "1"
DOC_SUNAT_CARNE_EXTRANJERIA = "4"
DOC_SUNAT_RUC = "6"
DOC_SUNAT_PASAPORTE = "7"

_DOC_SUNAT_POR_TIPO_PERSONA = {
    "dni": DOC_SUNAT_DNI,
    "ce": DOC_SUNAT_CARNE_EXTRANJERIA,
    "pasaporte": DOC_SUNAT_PASAPORTE,
}


def doc_sunat_de_persona(tipo_documento: str) -> str:
    return _DOC_SUNAT_POR_TIPO_PERSONA.get(tipo_documento, DOC_SUNAT_SIN_DOCUMENTO)


def tipo_comprobante(tipo_cliente: str | None, ruc: str | None) -> str:
    """Factura solo si el cliente es jurídico y tiene RUC; en todo otro
    caso boleta, incluido el cliente anónimo (RN-PER-005)."""
    return "factura" if tipo_cliente == "juridico" and ruc else "boleta"


LARGO_RUC = 11
LARGO_DNI = 8
SIN_DOCUMENTO = "00000000"


def cliente_identificado(numero_documento: str | None) -> bool:
    """Un cliente cuenta como *identificado* solo si dio un documento real.

    Vacío o el genérico `00000000` no cuentan (RN-PTS-002): el cliente
    existe, se le vende y se le entrega, pero queda fuera de las promociones
    y beneficios reservados a clientes registrados con documento. Sin esto,
    cualquier boleta anónima entraría al programa de puntos.
    """
    return bool(numero_documento) and numero_documento != SIN_DOCUMENTO


def documento_receptor_valido(num_doc: str | None) -> bool:
    """Vacío es válido (boleta a clientes varios). Con algo escrito, solo
    se aceptan 8 dígitos (DNI) u 11 (RUC): un documento a medio teclear
    haría rebotar el comprobante recién en SUNAT."""
    if not num_doc:
        return True
    return num_doc.isdigit() and len(num_doc) in (LARGO_DNI, LARGO_RUC)


def tipo_comprobante_por_documento(num_doc: str | None) -> str:
    """Lo que el cajero teclea decide el tipo: 11 dígitos es RUC y obliga
    factura; DNI, `00000000` o vacío van a boleta (RN-CPP-003).

    Convive con `tipo_comprobante`: esta gana cuando el PDV informó un
    documento, aquella cuando la venta trae `cliente_id` registrado.
    """
    return "factura" if num_doc and len(num_doc) == LARGO_RUC else "boleta"


# --- Cumplimiento de pedido (PROC-OPE-002) -----------------------------------
# Secuencia estricta, sin retroceso (RN-CUP-002): el avance mostrado en
# todas las pantallas es la verdad única del ítem (RN-CUP-003).
ORDEN_PREPARACION = ["pendiente", "en_preparacion", "listo", "entregado"]


def transicion_preparacion_valida(actual: str, nuevo: str) -> bool:
    """Solo se avanza al estado inmediatamente siguiente."""
    return (
        nuevo in ORDEN_PREPARACION
        and ORDEN_PREPARACION.index(nuevo) == ORDEN_PREPARACION.index(actual) + 1
    )


def estado_pedido(estados_items: list[str]) -> str:
    """Estado agregado del pedido para la pantalla de despacho:
    `listo` cuando TODOS los ítems están al menos listos; `entregado`
    cuando todos entregados; si no, el estado del ítem más atrasado."""
    if not estados_items:
        return "pendiente"
    return min(estados_items, key=ORDEN_PREPARACION.index)


def pedido_entregable(estados_items: list[str]) -> bool:
    """Solo se entrega un pedido con todos sus ítems al menos `listo`
    (RN-CUP-005). Un pedido sin ítems no es entregable."""
    return bool(estados_items) and all(
        estado in ("listo", "entregado") for estado in estados_items
    )


def pedido_entregado(estados_items: list[str]) -> bool:
    return bool(estados_items) and all(
        estado == "entregado" for estado in estados_items
    )


# --- Atributos y variantes (ADR-055) -----------------------------------------

MODOS_VARIANTE = {"siempre", "dinamica", "nunca"}
"""Si la combinación se materializa como fila hija de `producto_comercial`.

Es el `create_variant` de `product.attribute` en Odoo
(`always` | `dynamic` | `no_variant`), y elegir mal es lo que rompe un
catálogo de pizzas:

- `siempre` — se generan todas las combinaciones al vincular el atributo.
  Hace falta cuando cada una tiene precio o receta propios (Tamaño).
- `dinamica` — la fila se crea la primera vez que se vende esa combinación.
- `nunca` — no se genera fila. El valor viaja en la línea de venta y solo
  filtra líneas de receta. Es lo correcto para Mitad 1 / Mitad 2: con
  `siempre` serían 19 x 19 = 361 filas de producto por tamaño.
"""

DISPLAYS_ATRIBUTO = {"radio", "pildoras", "select", "color"}
"""Cómo lo dibuja el PDV. No cambia ninguna aritmética — igual que
`producto_opcion_grupo` no tiene `tipo` (ADR-035 §5) — pero 19 valores en
botones de radio es una pantalla inusable y en desplegable no."""


def combinaciones_a_generar(modo_variante: str) -> bool:
    """¿Este atributo materializa filas de producto al vincularse?

    Solo `siempre`. `dinamica` las crea al vender y `nunca` no las crea.
    """
    return modo_variante == "siempre"


# --- Medios de pago (RN-MDP-001) ---------------------------------------------

TIPOS_MEDIO_PAGO = {
    "efectivo",
    "tarjeta_credito",
    "tarjeta_debito",
    "billetera_digital",
    "transferencia",
    "cheque",
    "credito_empresarial",
}
"""Con qué paga el cliente. El tipo no es cosmética: `efectivo` es el único
que tiene cajón detrás —da vuelto y entra a la cadena de custodia
(RN-MDP-002)— y `credito_empresarial` es el único que puede cotizar contra
otra lista de precios (RN-MDP-001)."""

DIRECCIONES_MEDIO_PAGO = {"cobro", "pago", "ambos"}
"""De qué lado del mostrador se usa. El PDV solo ofrece los de `cobro` (y
`ambos`): un medio con el que se le paga a un proveedor no es una forma de
cobrarle a un comensal."""


# --- Cupón de promoción (ADR-061) --------------------------------------------
ESTADOS_CUPON = {"activo", "canjeado"}


def vencimiento_cupon(emitido: date, dias: int) -> date:
    """Hasta cuándo vale un cupón emitido hoy.

    El último día cuenta entero: un cupón de 30 días emitido el 1 vale
    hasta el 30 inclusive, que es como lo lee quien lo tiene en la mano.
    """
    return emitido + timedelta(days=max(dias, 1) - 1)


def cupon_vigente(estado: str, vigente_hasta: date, hoy: date) -> bool:
    """Vencer no es un estado que alguien registre, es una comparación.

    Guardarlo como estado obligaría a una tarea periódica que barra los
    vencidos, y el día que esa tarea no corra la base diría que un cupón de
    hace tres meses sigue vivo.
    """
    return estado == "activo" and vigente_hasta >= hoy


def promocion_emite(estado: str, vigente_hasta: date, hoy: date) -> bool:
    """¿La promoción todavía emite cupones nuevos?

    `terminada` es el derecho que la empresa se reserva de cortarla en
    cualquier momento. No toca los cupones ya emitidos: quien alcanzó a
    registrarse cumplió su parte, y retirarle el beneficio después sería
    cambiar el trato a mitad de camino.
    """
    return estado == "activa" and vigente_hasta >= hoy
