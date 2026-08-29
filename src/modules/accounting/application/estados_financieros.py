"""Casos de uso: balance de comprobación, libro mayor, Estado de Situación
Financiera y Estado de Resultados.

Los cuatro son **consulta pura**: se calculan agregando `asiento_linea` cada
vez que se piden, sin tabla de saldos propia. Un saldo materializado es un
segundo lugar donde vive la verdad, y el día que se desincroniza del mayor
nadie sabe cuál de los dos leer. Si algún día la agregación pesa, el remedio
es un índice o una vista materializada, no una tabla que se escribe a mano.

Ninguno filtra por `asiento.estado`: ver la nota de `LibroRepo`.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.accounting.domain import estados_financieros as ef
from src.modules.accounting.infrastructure.repositories import LibroRepo

CERO = Decimal("0.00")


def _saldo_natural(tipo_seccion: str, debe: Decimal, haber: Decimal) -> Decimal:
    return debe - haber if tipo_seccion == "deudora" else haber - debe


def balance_comprobacion(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Sumas y saldos por cuenta — el papel de trabajo con el que el contador
    externo arma todo lo demás, y el primer sitio donde se ve si el libro
    cuadra."""
    filas = LibroRepo(session).saldos(empresa_id, desde=desde, hasta=hasta)
    cuentas = []
    total_debe = total_haber = CERO
    for codigo, nombre, tipo, debe, haber in filas:
        saldo = debe - haber
        total_debe += debe
        total_haber += haber
        cuentas.append(
            {
                "codigo": codigo,
                "nombre": nombre,
                "tipo": tipo,
                "debe": debe,
                "haber": haber,
                "saldo_deudor": saldo if saldo > 0 else CERO,
                "saldo_acreedor": -saldo if saldo < 0 else CERO,
            }
        )
    return {
        "desde": desde,
        "hasta": hasta,
        "cuentas": cuentas,
        "total_debe": total_debe,
        "total_haber": total_haber,
        "cuadra": total_debe == total_haber,
    }


def libro_mayor(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    cuenta_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Movimientos de una cuenta con saldo corrido, en orden de fecha."""
    saldo = CERO
    movimientos = []
    for fecha, asiento_id, glosa, estado, tipo, monto in LibroRepo(session).movimientos(
        empresa_id, cuenta_id, desde=desde, hasta=hasta
    ):
        saldo += monto if tipo == "debe" else -monto
        movimientos.append(
            {
                "fecha": fecha,
                "asiento_id": asiento_id,
                "glosa": glosa,
                "estado": estado,
                "debe": monto if tipo == "debe" else CERO,
                "haber": monto if tipo == "haber" else CERO,
                "saldo": saldo,
            }
        )
    return {
        "cuenta_id": cuenta_id,
        "desde": desde,
        "hasta": hasta,
        "movimientos": movimientos,
        "saldo_final": saldo,
    }


def _resultado_del_libro(filas) -> Decimal:
    """Resultado del ejercicio leído del mayor completo, sin pasar por
    ninguna clasificación.

    Suma todo lo que es resultado —elementos 6, 7, 8 y 9, incluida la 79—.
    La reclasificación por función se cancela sola (el cargo al elemento 9
    contra el abono a la 79), así que incluirla no distorsiona nada y
    excluirla a medias sí. Es el número contra el que se contrasta el Estado
    de Resultados armado por líneas: si no coinciden, hay una cuenta que
    ninguna línea reclama.
    """
    resultado = CERO
    for _codigo, _nombre, tipo, debe, haber in filas:
        if tipo == "ingreso":
            resultado += haber - debe
        elif tipo == "gasto":
            resultado -= debe - haber
    return resultado


def _acumular(filas, secciones, *, incluir) -> tuple[dict, list[str]]:
    """Reparte los saldos en las líneas de `secciones`. Devuelve el mapa
    `(seccion, linea) → monto` y los códigos que ninguna línea reclamó."""
    montos: dict[tuple[str, str], Decimal] = {}
    naturalezas = {s.clave: s.naturaleza for s in secciones}
    sin_clasificar: list[str] = []
    for codigo, _nombre, tipo, debe, haber in filas:
        if not incluir(codigo, tipo):
            continue
        destino = ef.linea_de(codigo, secciones)
        if destino is None:
            sin_clasificar.append(codigo)
            continue
        monto = _saldo_natural(naturalezas[destino[0]], debe, haber)
        montos[destino] = montos.get(destino, CERO) + monto
    return montos, sin_clasificar


def _armar(secciones, montos) -> list[dict]:
    salida = []
    for seccion in secciones:
        lineas = [
            {
                "clave": linea.clave,
                "etiqueta": linea.etiqueta,
                "monto": montos.get((seccion.clave, linea.clave), CERO),
            }
            for linea in seccion.lineas
        ]
        salida.append(
            {
                "clave": seccion.clave,
                "etiqueta": seccion.etiqueta,
                "naturaleza": seccion.naturaleza,
                "lineas": lineas,
                "total": sum((linea["monto"] for linea in lineas), CERO),
            }
        )
    return salida


def estado_situacion_financiera(
    session: Session, *, empresa_id: uuid.UUID, hasta: date | None = None
) -> dict:
    """Balance a una fecha: activo contra pasivo más patrimonio.

    Los saldos son **acumulados desde el inicio del libro**, no del ejercicio:
    el ERP no genera todavía el asiento de cierre anual que traslada el
    resultado a resultados acumulados (elemento 89 contra la 59), así que el
    resultado se presenta como línea propia del patrimonio con todo lo
    acumulado. El balance cuadra igual; lo que falta es el corte por
    ejercicio, anotado como deuda en ROADMAP.
    """
    filas = LibroRepo(session).saldos(empresa_id, hasta=hasta)
    montos, sin_clasificar = _acumular(
        filas, ef.ESF, incluir=lambda codigo, tipo: tipo in ("activo", "pasivo", "patrimonio")
    )
    secciones = _armar(ef.ESF, montos)
    por_clave = {s["clave"]: s for s in secciones}

    resultado = _resultado_del_libro(filas)
    patrimonio = por_clave["patrimonio"]
    patrimonio["lineas"].append(
        {
            "clave": "resultado_ejercicio",
            "etiqueta": "Resultado del ejercicio (acumulado)",
            "monto": resultado,
        }
    )
    patrimonio["total"] += resultado

    total_activo = sum((por_clave[c]["total"] for c in ef.SECCIONES_ACTIVO), CERO)
    total_pasivo = sum((por_clave[c]["total"] for c in ef.SECCIONES_PASIVO), CERO)
    total_pasivo_patrimonio = total_pasivo + patrimonio["total"]
    return {
        "hasta": hasta,
        "secciones": secciones,
        "total_activo": total_activo,
        "total_pasivo": total_pasivo,
        "total_patrimonio": patrimonio["total"],
        "total_pasivo_patrimonio": total_pasivo_patrimonio,
        "descuadre": total_activo - total_pasivo_patrimonio,
        "cuadra": total_activo == total_pasivo_patrimonio,
        "cuentas_sin_clasificar": sorted(set(sin_clasificar)),
    }


def estado_resultados(
    session: Session,
    *,
    empresa_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Estado de Resultados por naturaleza del periodo.

    Los bloques cierran con un subtotal **acumulado** (resultado de
    explotación → antes de impuestos → del ejercicio), que es como lo lee
    quien decide: cada línea siguiente corrige el número anterior.
    """
    filas = LibroRepo(session).saldos(empresa_id, desde=desde, hasta=hasta)
    todas_las_secciones = tuple(
        seccion for _clave, _etiqueta, secciones in ef.BLOQUES_ER for seccion in secciones
    )
    montos, sin_clasificar = _acumular(
        filas,
        todas_las_secciones,
        incluir=lambda codigo, tipo: (
            tipo in ("ingreso", "gasto") and not ef.es_reclasificacion(codigo)
        ),
    )

    bloques = []
    acumulado = CERO
    for clave, etiqueta, secciones in ef.BLOQUES_ER:
        armadas = _armar(secciones, montos)
        for seccion in armadas:
            # Una sección acreedora suma al resultado (ingresos) y una deudora
            # lo resta (gastos): el signo sale de la naturaleza declarada, no
            # del nombre de la sección.
            signo = 1 if seccion["naturaleza"] == "acreedora" else -1
            acumulado += signo * seccion["total"]
        bloques.append(
            {
                "clave": clave,
                "etiqueta": etiqueta,
                "secciones": armadas,
                "subtotal": acumulado,
            }
        )

    control = _resultado_del_libro(filas)
    return {
        "desde": desde,
        "hasta": hasta,
        "bloques": bloques,
        "resultado_ejercicio": acumulado,
        "resultado_libro": control,
        "cuadra": acumulado == control,
        "cuentas_sin_clasificar": sorted(set(sin_clasificar)),
    }
