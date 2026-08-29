"""Promociones condicionales: alta, listado y aplicación automática
(ADR-076).

La aritmética vive en `domain/promociones.py` y no toca la base. Acá pasa lo
otro: qué reglas están vigentes para **este** pedido, y dejar el resultado en
`venta_promocion`.
"""

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.modules.sales.application.errors import Conflicto, NoEncontrado, ReglaNegocio
from src.modules.sales.domain import promociones as reglas_promo
from src.modules.sales.infrastructure.models import (
    ProductoComercial,
    Promocion,
    Venta,
    VentaItem,
    VentaPromocion,
)
from src.modules.users.infrastructure.models import Sucursal
from src.shared import fechas


# --- Alta y administración ----------------------------------------------------
def crear_promocion(session: Session, *, empresa_id: uuid.UUID, **campos) -> Promocion:
    _validar(campos)
    promocion = Promocion(empresa_id=empresa_id, **campos)
    session.add(promocion)
    session.flush()
    return promocion


def editar_promocion(
    session: Session, promocion_id: uuid.UUID, **campos
) -> Promocion:
    promocion = _exigir(session, promocion_id)
    combinado = {
        "tipo": promocion.tipo,
        "condicion": promocion.condicion,
        "beneficio": promocion.beneficio,
        **{k: v for k, v in campos.items() if v is not None},
    }
    _validar(combinado)
    for campo, valor in campos.items():
        setattr(promocion, campo, valor)
    return promocion


def terminar_promocion(session: Session, promocion_id: uuid.UUID) -> Promocion:
    """La apaga; no la borra (RN-PRM-005).

    Las ventas que la aplicaron siguen apuntándola, y el reporte tiene que
    poder nombrarla. Apagarla no toca ninguna venta ya cobrada: lo aplicado
    quedó congelado en `venta_promocion`.
    """
    promocion = _exigir(session, promocion_id)
    promocion.activa = False
    return promocion


def listar_promociones(
    session: Session, *, empresa_id: uuid.UUID, solo_activas: bool = False
) -> list[Promocion]:
    q = select(Promocion).where(
        Promocion.empresa_id == empresa_id, Promocion.deleted_at.is_(None)
    )
    if solo_activas:
        q = q.where(Promocion.activa.is_(True))
    return list(session.scalars(q.order_by(Promocion.prioridad.desc(), Promocion.nombre)))


def _exigir(session: Session, promocion_id: uuid.UUID) -> Promocion:
    promocion = session.get(Promocion, promocion_id)
    if promocion is None or promocion.deleted_at is not None:
        raise NoEncontrado("promoción no encontrada")
    return promocion


def _validar(campos: dict) -> None:
    """Lo que no puede quedar en la base aunque el formulario lo mande.

    La forma de `condicion`/`beneficio` la valida Pydantic en la API; acá
    quedan las reglas que cruzan campos, que un esquema por campo no ve.
    """
    tipo = campos.get("tipo")
    if tipo not in reglas_promo.TIPOS:
        raise ReglaNegocio(f"tipo de promoción inválido: {tipo}")
    desde, hasta = campos.get("desde"), campos.get("hasta")
    if desde and hasta and hasta < desde:
        raise ReglaNegocio("la vigencia termina antes de empezar")
    beneficio = campos.get("beneficio") or {}
    pct = beneficio.get("descuento_pct")
    if pct is not None and not (0 < Decimal(str(pct)) <= 100):
        raise ReglaNegocio("el porcentaje de descuento va entre 0 y 100")
    if tipo == "nxm":
        lleva = int((campos.get("condicion") or {}).get("lleva") or 0)
        libera = int(beneficio.get("libera") or 0)
        if libera >= lleva:
            raise ReglaNegocio(
                "una promoción N×M tiene que liberar menos de lo que exige llevar"
            )


# --- Aplicación ---------------------------------------------------------------
def _del_alcance(promocion: Promocion, venta: Venta, marca_id: uuid.UUID | None) -> bool:
    if promocion.sucursal_id and promocion.sucursal_id != venta.sucursal_id:
        return False
    if promocion.marca_id and promocion.marca_id != marca_id:
        return False
    if promocion.canales and venta.canal not in promocion.canales:
        return False
    return not (promocion.modalidades and venta.modalidad not in promocion.modalidades)


def vigentes_para(
    session: Session,
    venta: Venta,
    *,
    dia: date | None = None,
    hora: time | None = None,
) -> list[reglas_promo.Regla]:
    """Las promociones que corren para esta venta, ahora.

    `dia`/`hora` entran por parámetro —con la hora del negocio por defecto,
    no la del servidor— para que un test pueda pararse un martes a las 20:00
    sin tocar el reloj del proceso.
    """
    sucursal = session.get(Sucursal, venta.sucursal_id)
    if sucursal is None:
        return []
    momento = fechas.hoy() if dia is None else dia
    reloj = hora if hora is not None else fechas.ahora().time()

    candidatas = session.scalars(
        select(Promocion).where(
            Promocion.empresa_id == sucursal.empresa_id,
            Promocion.activa.is_(True),
            Promocion.deleted_at.is_(None),
        )
    )
    return [
        reglas_promo.Regla(
            id=str(p.id),
            nombre=p.nombre,
            tipo=p.tipo,
            condicion=p.condicion or {},
            beneficio=p.beneficio or {},
            prioridad=p.prioridad,
            acumulable=p.acumulable,
        )
        for p in candidatas
        if _del_alcance(p, venta, sucursal.marca_id)
        and reglas_promo.vigente(
            desde=p.desde,
            hasta=p.hasta,
            dias_semana=p.dias_semana,
            hora_desde=p.hora_desde,
            hora_hasta=p.hora_hasta,
            dia=momento,
            hora=reloj,
        )
    ]


def _lineas_de(session: Session, venta_id: uuid.UUID) -> list[reglas_promo.LineaPromocionable]:
    """Los platos del pedido. **Los extras no entran**: son línea propia
    (RN-COM-021) pero no se piden solos, y dejarlos participar haría que un
    2x1 de pizzas regalara un queso extra."""
    filas = session.execute(
        select(VentaItem, ProductoComercial)
        .join(
            ProductoComercial,
            ProductoComercial.id == VentaItem.producto_comercial_id,
        )
        .where(VentaItem.venta_id == venta_id, VentaItem.padre_venta_item_id.is_(None))
    )
    return [
        reglas_promo.LineaPromocionable(
            venta_item_id=str(item.id),
            producto_id=str(item.producto_comercial_id),
            categoria_id=str(prod.categoria_id) if prod.categoria_id else None,
            cantidad=int(item.cantidad),
            precio_unitario=item.precio_unitario,
        )
        for item, prod in filas
    ]


def recalcular_promociones(
    session: Session,
    venta: Venta,
    *,
    dia: date | None = None,
    hora: time | None = None,
) -> Decimal:
    """Vuelve a evaluar las promociones del pedido y devuelve lo descontado.

    **Idempotente y destructivo**: borra lo aplicado y lo calcula de nuevo.
    Es lo que permite llamarla desde los cuatro caminos que cambian un pedido
    —crear, agregar líneas, quitar líneas y mover— sin llevar la cuenta de
    qué se activó antes. Una promoción que dejó de cumplirse porque el cajero
    quitó una pizza desaparece sola, que es lo correcto.

    Un consumo de personal no promociona: ya vale cero (RN-COM-025).
    """
    session.execute(
        delete(VentaPromocion).where(VentaPromocion.venta_id == venta.id),
        execution_options={"synchronize_session": False},
    )
    if venta.tipo != "venta":
        return Decimal(0)

    aplicaciones = reglas_promo.aplicar(
        vigentes_para(session, venta, dia=dia, hora=hora),
        _lineas_de(session, venta.id),
    )
    for aplicacion in aplicaciones:
        session.add(
            VentaPromocion(
                venta_id=venta.id,
                promocion_id=uuid.UUID(aplicacion.regla_id),
                nombre=aplicacion.nombre,
                monto=aplicacion.monto,
                detalle=aplicacion.consumo,
            )
        )
    session.flush()
    return reglas_promo.total_promociones(aplicaciones)


def total_aplicado(session: Session, venta_id: uuid.UUID) -> Decimal:
    """Lo que las promociones le bajan a esta venta, ya calculado."""
    filas = session.scalars(
        select(VentaPromocion.monto).where(VentaPromocion.venta_id == venta_id)
    )
    return sum(filas, Decimal(0))


def aplicadas_a(session: Session, venta_id: uuid.UUID) -> list[VentaPromocion]:
    return list(
        session.scalars(
            select(VentaPromocion)
            .where(VentaPromocion.venta_id == venta_id)
            .order_by(VentaPromocion.nombre)
        )
    )


def exigir_promocion_de_empresa(
    session: Session, promocion_id: uuid.UUID, empresa_id: uuid.UUID | None
) -> Promocion:
    promocion = _exigir(session, promocion_id)
    if empresa_id is not None and promocion.empresa_id != empresa_id:
        raise Conflicto("la promoción es de otra empresa")
    return promocion
