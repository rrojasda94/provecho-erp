"""Motor de sincronización del hub (ADR-009, fase 2).

Un ciclo = **empujar y después jalar**, en ese orden y nunca al revés: si
el hub jalara primero, sobreescribiría su stock local con el de una nube
que todavía no sabe nada de las ventas del corte, y recién al ciclo
siguiente convergería. Empujando primero, la nube procesa las ventas
—descuenta su propio stock, prepara los comprobantes— y lo que vuelve en
el pull ya es el estado correcto.

Ninguna falla de sync puede frenar el local: si la nube no responde, el
ciclo anota el error y termina. El hub sigue vendiendo contra su base.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.database import SessionLocal
from src.core.sync import estado_conexion, importador, registro, watermark
from src.core.sync.cliente_nube import ClienteNube, ErrorNube
from src.core.sync.contratos import PULL, PUSH, AlcanceHub

log = logging.getLogger("provecho.sync")

# Techo de páginas por recurso en un ciclo: una carga inicial grande
# termina en el ciclo siguiente en vez de bloquear el proceso.
MAX_PAGINAS = 50
# Cuánto puede ensancharse una página ante muchas filas con la MISMA marca
# (un seed inserta cientos con el `now()` de la transacción). Sin esto, un
# bloque de filas empatadas más grande que el lote no avanzaría nunca.
FACTOR_DESEMPATE = 16


def alcance_del_hub() -> AlcanceHub:
    try:
        return AlcanceHub(
            empresa_id=uuid.UUID(settings.hub_empresa_id),
            sucursal_id=uuid.UUID(settings.hub_sucursal_id),
        )
    except ValueError as e:
        raise ValueError(
            "HUB_EMPRESA_ID y HUB_SUCURSAL_ID deben ser UUID válidos"
        ) from e


def _empujar_modulo(
    session: Session, cliente: ClienteNube, modulo, alcance: AlcanceHub, limite: int
) -> dict:
    recurso = modulo.RECURSO_PUSH
    desde = watermark.leer(session, PUSH, recurso)
    lote = modulo.pendientes(session, alcance, desde, limite)
    enviados = modulo.hay_pendientes(lote)
    if enviados == 0:
        watermark.registrar_ok(session, PUSH, recurso, None)
        return {"enviados": 0, "errores": []}

    try:
        respuesta = cliente.push({recurso: lote})
    except ErrorNube as e:
        watermark.registrar_error(session, PUSH, recurso, str(e))
        return {"enviados": 0, "error": str(e)}

    errores = respuesta.get("errores", [])
    if errores:
        # No se avanza la marca: el lote entero se reintenta al ciclo
        # siguiente (todo el camino ascendente es idempotente). Un ítem que
        # la nube rechaza siempre frena su recurso a propósito — perderlo en
        # silencio sería perder una venta.
        watermark.registrar_error(
            session, PUSH, recurso, f"{len(errores)} ítems rechazados: {errores[:3]}"
        )
    else:
        watermark.registrar_ok(
            session, PUSH, recurso, datetime.fromisoformat(lote["marca"])
        )
    log.info("sync push %s: %s ítems, %s rechazados", recurso, enviados, len(errores))
    return {"enviados": enviados, "errores": errores, "aplicado": respuesta}


def empujar(
    session: Session, cliente: ClienteNube, alcance: AlcanceHub, limite: int
) -> dict:
    """Reproduce en la nube lo que el local hizo durante el corte.

    Un módulo por vez y con su propio watermark: si `inventory` se traba con
    una recepción que la nube rechaza, las ventas siguen subiendo. Que un
    conteo bloquee el cobro sería exactamente al revés de lo que importa.
    """
    total = {"enviados": 0, "errores": [], "por_modulo": {}}
    for modulo in registro.MODULOS_PUSH:
        resultado = _empujar_modulo(session, cliente, modulo, alcance, limite)
        total["enviados"] += resultado.get("enviados", 0)
        total["errores"].extend(resultado.get("errores", []))
        total["por_modulo"][modulo.RECURSO_PUSH] = resultado
    return total


def _jalar_recurso(
    session: Session, cliente: ClienteNube, recurso, limite: int
) -> int:
    desde = watermark.leer(session, PULL, recurso.nombre)
    aplicadas_total = 0
    pagina = limite
    for _ in range(MAX_PAGINAS):
        filas = cliente.pull(recurso.nombre, desde, pagina)["filas"]
        aplicadas, marca = importador.importar(session, recurso, filas)
        aplicadas_total += aplicadas
        if len(filas) < pagina:
            watermark.registrar_ok(session, PULL, recurso.nombre, marca)
            return aplicadas_total
        if marca is not None and (desde is None or marca > desde):
            watermark.registrar_ok(session, PULL, recurso.nombre, marca)
            desde = marca
            pagina = limite
        elif pagina < limite * FACTOR_DESEMPATE:
            pagina *= 2  # página entera con la misma marca: ensanchar
        else:
            raise ErrorNube(
                f"{recurso.nombre}: más de {pagina} filas con la misma marca"
            )
    raise ErrorNube(f"{recurso.nombre}: paginación sin terminar en {MAX_PAGINAS} páginas")


def jalar(session: Session, cliente: ClienteNube, limite: int) -> dict:
    """Trae de la nube el catálogo, el stock y el RBAC del local.

    Un recurso que falla no cancela los demás: mejor un hub con catálogo
    fresco y stock viejo que uno sin nada.
    """
    resultado = {"filas": 0, "errores": []}
    for recurso in registro.RECURSOS:
        try:
            # SAVEPOINT por recurso: lo que falla se deshace solo, lo que ya
            # entró se conserva.
            with session.begin_nested():
                resultado["filas"] += _jalar_recurso(session, cliente, recurso, limite)
        except (ErrorNube, SQLAlchemyError) as e:
            log.warning("sync pull %s: %s", recurso.nombre, e)
            watermark.registrar_error(session, PULL, recurso.nombre, str(e))
            resultado["errores"].append({"recurso": recurso.nombre, "detalle": str(e)})
    log.info("sync pull: %s filas, %s recursos con error",
             resultado["filas"], len(resultado["errores"]))
    return resultado


def ciclo(session_factory=SessionLocal, cliente: ClienteNube | None = None) -> dict:
    """Un ciclo completo. Devuelve el resumen que loguea el runner."""
    if not settings.es_hub:
        return {"ejecutado": False, "motivo": "deployment_mode=cloud"}

    conexion = estado_conexion.verificar_conectividad()
    if conexion["estado"] == estado_conexion.OFFLINE:
        return {"ejecutado": False, "motivo": "offline", "conexion": conexion}

    propio = cliente is None
    cliente = cliente or ClienteNube()
    alcance = alcance_del_hub()
    limite = settings.sync_lote_maximo
    try:
        with session_factory() as session:
            resumen = {
                "ejecutado": True,
                "conexion": conexion,
                "push": empujar(session, cliente, alcance, limite),
                "pull": jalar(session, cliente, limite),
            }
            session.commit()
            return resumen
    finally:
        if propio:
            cliente.cerrar()
