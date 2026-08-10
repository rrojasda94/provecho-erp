"""Situaciones de demo para el módulo de reportes (solo desarrollo).

Los reportes que había en la base eran de pruebas sueltas: títulos sin
entidad detrás, sin actor y sin destino. Con ADR-036 eso se nota — el botón
«ir al registro» lleva a un 404 y la columna «Quién» dice «Sistema» en todo.

Este seeder **borra los reportes viejos** y arma nueve situaciones que sí
existen: cada una crea la fila real (el ajuste, el lote, el cierre de caja) y
después publica el evento de verdad, así que el reporte pasa por el mismo
camino que en producción —resolución de destinatarios, entregas, bandeja— y
el enlace aterriza en un registro que se puede abrir.

Las entidades se insertan directo en vez de manejar cada caso de uso: la
demo necesita el *estado final* (un ajuste pendiente, un lote bloqueado, una
caja descuadrada), no reproducir el camino que lleva ahí, y encadenar ocho
módulos de casos de uso para pintar una pantalla es más frágil que el
resultado que se busca. Lo que **sí** pasa por el camino real es el reporte:
la emisión, la distribución y el escalamiento.

Idempotente: vuelve a arrancar de cero cada vez (borra y rehace).
**PROHIBIDO en producción** — igual que el resto de los seeders de demo.

Uso:
    python -m src.seeders.seed
    python -m src.seeders.pdv_demo
    python -m src.seeders.reportes_demo
"""

import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import src.core.models_registry  # noqa: F401
from src.config.settings import settings
from src.core.database import SessionLocal
from src.core.events import event_bus
from src.modules.accounting.infrastructure.models import (
    AperturaCaja,
    CierreCaja,
    MovimientoDinero,
)
from src.modules.inventory.infrastructure.models import (
    Ajuste,
    Articulo,
    Categoria,
    Devolucion,
    Lote,
    Sku,
    Stock,
    StockLote,
)
from src.modules.production.infrastructure.models import OrdenProduccion
from src.modules.reports.application import escalamientos as escalamientos_uc
from src.modules.reports.application import listeners as reports_listeners
from src.modules.reports.infrastructure.models import (
    EntregaReporte,
    ReporteEmitido,
    ReporteEscalamiento,
)
from src.modules.sales.infrastructure.models import PuntoVenta, Venta
from src.modules.users.application import listeners as users_listeners
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Notificacion,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin
from src.shared import fechas
from src.shared.models import Archivo

# Quién provoca cada hecho. Sin gente distinta, la columna «Quién» de la
# bandeja dice lo mismo en todas las filas y no se entiende para qué está.
# El PIN es el mismo para todos: es una demo, no un entorno con secretos.
PIN_DEMO = "654321"
EQUIPO = [
    ("almacenero1", "almacenero", "Nadia Flores"),
    ("cajero1", "cajero", "Beto Salas"),
    ("supervisor1", "supervisor", "Ivana Ruiz"),
    ("jefecocina1", "jefe_cocina", "Marco Tello"),
    ("contador1", "contador", "Lucía Paredes"),
]


def _usuario(session: Session, username: str, rol_nombre: str, display: str,
             sucursal: Sucursal) -> Usuario:
    usuario = session.scalar(select(Usuario).where(Usuario.username == username))
    if usuario is None:
        usuario = Usuario(
            username=username,
            pin_hash=hash_pin(PIN_DEMO),
            tipo="humano",
            nombre_display=display,
        )
        session.add(usuario)
        session.flush()
    rol = session.scalar(select(Rol).where(Rol.nombre == rol_nombre))
    if rol is not None and session.get(UsuarioRol, (usuario.id, rol.id)) is None:
        session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))
    # Sin sucursal el JWT no lleva empresa y el contexto de tenant le niega
    # todo (ADR-004) — incluida su propia bandeja.
    if session.get(UsuarioSucursal, (usuario.id, sucursal.id)) is None:
        session.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
    return usuario


def borrar_lo_viejo(session: Session) -> dict[str, int]:
    """Deja la pizarra limpia: los reportes y los hechos que los provocaron.

    El orden importa: el escalamiento apunta al reporte con `RESTRICT`, así
    que borrar el reporte primero falla por integridad — que es exactamente
    lo que esa FK existe para impedir.

    Los hechos se identifican por **quién los creó**: los cinco usuarios de
    `EQUIPO` no los usa nada más que este seeder, así que "lo que tocó el
    equipo de demo" es un criterio exacto y no una heurística sobre textos.
    Sin esto, correrlo dos veces choca contra el unique de `lote`.
    """
    contados = {
        "escalamientos": len(list(session.scalars(select(ReporteEscalamiento.id)))),
        "reportes": len(list(session.scalars(select(ReporteEmitido.id)))),
    }
    session.execute(delete(ReporteEscalamiento))
    session.execute(delete(EntregaReporte))
    session.execute(delete(ReporteEmitido))
    # La bandeja del usuario vive en `users` y la llena el listener; sin
    # limpiarla quedarían notificaciones apuntando a reportes que ya no están.
    borradas = session.execute(
        delete(Notificacion).where(Notificacion.referencia_tipo == "reporte_emitido")
    )
    contados["notificaciones"] = borradas.rowcount or 0

    demo = list(
        session.scalars(
            select(Usuario.id).where(
                Usuario.username.in_([u for u, _, _ in EQUIPO])
            )
        )
    )
    contados["hechos"] = _borrar_hechos(session, demo) if demo else 0
    session.commit()
    return contados


def _borrar_hechos(session: Session, usuarios: list) -> int:
    """Los hechos de la corrida anterior, de hijo a padre."""
    lotes = list(
        session.scalars(select(Lote.id).where(Lote.codigo.like("L-DEMO-%")))
    )
    aperturas = list(
        session.scalars(
            select(AperturaCaja.id).where(AperturaCaja.cajero_id.in_(usuarios))
        )
    )
    borrados = 0
    for sentencia in (
        delete(StockLote).where(StockLote.lote_id.in_(lotes)) if lotes else None,
        delete(Lote).where(Lote.id.in_(lotes)) if lotes else None,
        delete(Archivo).where(Archivo.subido_por.in_(usuarios)),
        delete(Ajuste).where(Ajuste.solicitado_por.in_(usuarios)),
        delete(Devolucion).where(Devolucion.registrado_por.in_(usuarios)),
        delete(OrdenProduccion).where(OrdenProduccion.creado_por.in_(usuarios)),
        delete(MovimientoDinero).where(MovimientoDinero.solicitado_por.in_(usuarios)),
        (
            delete(CierreCaja).where(CierreCaja.apertura_caja_id.in_(aperturas))
            if aperturas
            else None
        ),
        delete(AperturaCaja).where(AperturaCaja.cajero_id.in_(usuarios)),
        delete(Venta).where(Venta.usuario_id.in_(usuarios)),
    ):
        if sentencia is not None:
            borrados += session.execute(sentencia).rowcount or 0
    return borrados


def _sku_demo(session: Session, empresa: Empresa) -> Sku:
    articulo = session.scalar(
        select(Articulo).where(
            Articulo.empresa_id == empresa.id, Articulo.id_interno == "A001"
        )
    )
    if articulo is None:
        raise SystemExit("Corre primero `python -m src.seeders.pdv_demo`.")
    return session.scalar(select(Sku).where(Sku.articulo_id == articulo.id))


def _stock(session: Session, almacen: Almacen, sku: Sku, cantidad, minimo) -> Stock:
    fila = session.scalar(
        select(Stock).where(Stock.almacen_id == almacen.id, Stock.sku_id == sku.id)
    )
    if fila is None:
        fila = Stock(almacen_id=almacen.id, sku_id=sku.id)
        session.add(fila)
    fila.cantidad = Decimal(cantidad)
    fila.stock_minimo = Decimal(minimo)
    session.flush()
    return fila


def _venta(session: Session, sucursal: Sucursal, punto: PuntoVenta, usuario: Usuario,
           numero: int, clave: str, **campos) -> Venta:
    venta = Venta(
        sucursal_id=sucursal.id,
        punto_venta_id=punto.id,
        usuario_id=usuario.id,
        fecha_orden=fechas.hoy(),
        numero_orden=numero,
        canal="pdv",
        modalidad="mesa",
        idempotency_key=clave,
        **campos,
    )
    session.add(venta)
    session.flush()
    return venta


def sembrar_situaciones(session: Session, ctx: dict) -> list[str]:
    """Crea las filas reales y publica los eventos. Devuelve el guion de lo
    que quedó, para imprimirlo."""
    empresa, sucursal, punto = ctx["empresa"], ctx["sucursal"], ctx["punto"]
    almacen, sku = ctx["almacen"], ctx["sku"]
    # La medianoche del negocio, no la del proceso: un lote «vencido hace 4
    # días» tiene que serlo en la zona en la que opera el local.
    hoy = fechas.hoy()
    guion: list[str] = []

    # --- 1. Ajuste fuera de margen, pendiente de aprobar --------------------
    # La más accionable de todas: el reporte es urgente y la pantalla destino
    # tiene los botones de aprobar y rechazar.
    ajuste = Ajuste(
        almacen_id=almacen.id,
        sku_id=sku.id,
        cantidad=Decimal("-18.0000"),
        motivo="merma",
        solicitado_por=ctx["almacenero"].id,
        dentro_margen=False,
        estado="pendiente",
    )
    session.add(ajuste)
    session.flush()
    event_bus.publish(
        "inventory.ajuste_fuera_margen",
        {
            "ajuste_id": str(ajuste.id),
            "almacen_id": str(almacen.id),
            "aprobado_por": str(ctx["almacenero"].id),
            "sku_id": str(sku.id),
            "cantidad": "-18.0000",
            "motivo": "merma",
        },
        session=session,
    )
    guion.append("Ajuste fuera de margen (−18) pendiente de aprobar — Nadia Flores")

    # --- 2. Stock bajo mínimo ----------------------------------------------
    fila = _stock(session, almacen, sku, "6.0000", "25.0000")
    event_bus.publish(
        "inventory.stock_bajo_minimo",
        {
            "almacen_id": str(almacen.id),
            "sku_id": str(sku.id),
            "cantidad": str(fila.cantidad),
            "stock_minimo": str(fila.stock_minimo),
            "usuario_id": str(ctx["almacenero"].id),
        },
        session=session,
    )
    guion.append("Stock bajo mínimo: quedan 6 de 25 — Nadia Flores")

    # --- 3. Lote vencido bloqueado -----------------------------------------
    lote = Lote(
        articulo_id=sku.articulo_id,
        # Prefijo `L-DEMO-` para que la corrida siguiente sepa cuál borrar.
        codigo="L-DEMO-118",
        fecha_vencimiento=hoy - timedelta(days=4),
        origen="compra",
        referencia="OC-DEMO-118",
    )
    session.add(lote)
    session.flush()
    session.add(
        StockLote(
            almacen_id=almacen.id,
            sku_id=sku.id,
            lote_id=lote.id,
            cantidad=Decimal("9.0000"),
            estado="bloqueado",
        )
    )
    event_bus.publish(
        "inventory.lote_vencido_detectado",
        {
            "lote_id": str(lote.id),
            "almacen_id": str(almacen.id),
            "sku_id": str(sku.id),
            "fecha_vencimiento": (hoy - timedelta(days=4)).isoformat(),
            "cantidad": "9.0000",
            # Lo descubrió el barrido de las 06:00, no una persona: en la
            # bandeja va a decir «Sistema», y está bien que se distinga.
            "usuario_id": None,
        },
        session=session,
    )
    guion.append("Lote vencido hace 4 días, 9 unidades bloqueadas — Sistema")

    # --- 4. Conteo cíclico vencido -----------------------------------------
    categoria = session.scalar(
        select(Categoria).where(
            Categoria.empresa_id == empresa.id, Categoria.nombre == "Mercadería"
        )
    )
    categoria.frecuencia_conteo = "semanal"
    session.flush()
    event_bus.publish(
        "inventory.conteo_vencido",
        {
            "almacen_id": str(almacen.id),
            "categoria_id": str(categoria.id),
            "categoria": categoria.nombre,
            "frecuencia": "semanal",
            "fecha_programada": (hoy - timedelta(days=6)).isoformat(),
            "dias_atraso": 6,
            "dirigido_a": ["almacen", "gerencia"],
            "usuario_id": None,
        },
        session=session,
    )
    guion.append("Conteo de Mercadería con 6 días de atraso — Sistema")

    # --- 5. Devolución a proveedor -----------------------------------------
    devolucion = Devolucion(
        almacen_id=almacen.id,
        origen="proveedor",
        motivo="vencido",
        estado="registrada",
        reporte_dirigido_a="almacen",
        observacion="Llegaron 12 unidades a 3 días de vencer. Se rechaza el lote.",
        registrado_por=ctx["almacenero"].id,
    )
    session.add(devolucion)
    session.flush()
    event_bus.publish(
        "inventory.devolucion_a_proveedor",
        {
            "devolucion_id": str(devolucion.id),
            "almacen_id": str(almacen.id),
            "referencia_id": None,
            "motivo": "vencido",
            "destino": None,
            "reporte_dirigido_a": "almacen",
            "registrado_por": str(ctx["almacenero"].id),
            "items": [],
        },
        session=session,
    )
    guion.append("Devolución a proveedor por mercadería vencida — Nadia Flores")

    # --- 6 y 7. Dos ventas: una con descuento, una demorada ----------------
    con_descuento = _venta(
        session, sucursal, punto, ctx["cajero"], 1041, "demo-rep-1041",
        estado="pagada", total=Decimal("68.00"),
        descuento_modo="porcentaje", descuento_valor=Decimal("20.00"),
        descuento_motivo="Pedido demorado, se compensa al cliente",
        descuento_autorizado_por=ctx["supervisor"].id,
        referencia_atencion="Mesa 6",
    )
    event_bus.publish(
        "sales.descuento_aplicado",
        {
            "venta_id": str(con_descuento.id),
            "sucursal_id": str(sucursal.id),
            "modo": "porcentaje",
            "valor": "20.00",
            "motivo": "Pedido demorado, se compensa al cliente",
            "autorizado_por": str(ctx["supervisor"].id),
        },
        session=session,
    )
    guion.append("Descuento del 20% autorizado en el pedido #1041 — Ivana Ruiz")

    # `venta.estado` es el del cobro (`orden` = todavía no se pagó); el
    # estado de cocina vive en `venta_item` y es el que viaja en el evento.
    demorada = _venta(
        session, sucursal, punto, ctx["cajero"], 1042, "demo-rep-1042",
        estado="orden", total=Decimal("54.00"),
        referencia_atencion="Mesa 9",
    )
    event_bus.publish(
        "sales.pedido_demorado",
        {
            "venta_id": str(demorada.id),
            "sucursal_id": str(sucursal.id),
            "minutos_umbral": 15,
            "minutos_transcurridos": 41,
            "estado": "en_preparacion",
            "items_pendientes": 2,
        },
        session=session,
    )
    guion.append("Pedido #1042 demorado 41 min (umbral 15) — Sistema")

    # --- 8. Cierre de caja irregular ---------------------------------------
    apertura = AperturaCaja(
        punto_venta_id=punto.id,
        cajero_id=ctx["cajero"].id,
        relevo_encargado_id=ctx["supervisor"].id,
        monto_apertura=Decimal("150.00"),
        detalle_denominaciones={"50": 3},
    )
    session.add(apertura)
    session.flush()
    cierre = CierreCaja(
        apertura_caja_id=apertura.id,
        cajero_id=ctx["cajero"].id,
        montos_esperados={"efectivo": "740.00", "tarjeta": "310.00"},
        montos_reales={"efectivo": "704.50", "tarjeta": "310.00"},
        descuadre_monto=Decimal("-35.50"),
        descuadre_atribucion="cajero",
        estado="con_irregularidad",
        # A dónde va el efectivo, no en qué tramo de la cadena está: eso
        # último vive en `custodia_efectivo.estado`, que es otra tabla.
        custodia="local_caja_fuerte",
        relevos=[
            {"rol": "cajero", "usuario_id": str(ctx["cajero"].id)},
            {"rol": "encargado", "usuario_id": str(ctx["supervisor"].id)},
        ],
    )
    session.add(cierre)
    session.flush()
    event_bus.publish(
        "accounting.cierre_caja_irregular",
        {
            "cierre_caja_id": str(cierre.id),
            "sucursal_id": str(sucursal.id),
            "cerrado_por": str(ctx["supervisor"].id),
            "cajero_id": str(ctx["cajero"].id),
            "descuadre_monto": "-35.50",
            "descuadre_tarjeta": "0.00",
            "descuadre_atribucion": "cajero",
        },
        session=session,
    )
    guion.append("Cierre de caja con faltante de S/ 35.50 — Ivana Ruiz")

    # --- 9. Pago sobre umbral esperando aprobación -------------------------
    pago = MovimientoDinero(
        empresa_id=empresa.id,
        tipo="egreso",
        concepto="pago_proveedor",
        monto=Decimal("4800.00"),
        estado="pendiente",
        solicitado_por=ctx["contador"].id,
    )
    session.add(pago)
    session.flush()
    event_bus.publish(
        "accounting.pago_requiere_aprobacion",
        {
            "movimiento_dinero_id": str(pago.id),
            "empresa_id": str(empresa.id),
            "proveedor_id": None,
            "monto": "4800.00",
            "umbral": "3000.00",
            "solicitado_por": str(ctx["contador"].id),
        },
        session=session,
    )
    guion.append("Pago de S/ 4800 sobre el umbral de S/ 3000 — Lucía Paredes")

    # --- 10. No conformidad de producción ----------------------------------
    orden = OrdenProduccion(
        articulo_id=sku.articulo_id,
        almacen_id=almacen.id,
        cantidad_planeada=Decimal("40.0000"),
        estado="no_conforme_desechado",
        merma_cantidad=Decimal("40.0000"),
        merma_motivo="Masa fermentada de más: sabor ácido en toda la tanda",
        evidencia_destruccion_url="https://demo.local/evidencia/tanda-118.mp4",
        creado_por=ctx["jefe_cocina"].id,
        idempotency_key="demo-rep-prod-118",
    )
    session.add(orden)
    session.flush()
    event_bus.publish(
        "production.no_conformidad_detectada",
        {
            "orden_produccion_id": str(orden.id),
            "almacen_id": str(almacen.id),
            "resultado": "no_conforme_desechado",
            "registrado_por": str(ctx["jefe_cocina"].id),
        },
        session=session,
    )
    guion.append("Tanda de 40 desechada por no conformidad — Marco Tello")
    ctx["orden_produccion"] = orden

    session.commit()
    return guion


def sembrar_escalamientos(session: Session, ctx: dict) -> list[str]:
    """Tres cadenas en distinto estado. Una sola no muestra nada: lo que hay
    que poder ver de un vistazo es qué está abierto, qué subió de nivel y qué
    terminó.

    **Cada cadena la abre y la cierra alguien que de verdad puede.** La doble
    puerta de RN-REP-002 también aplica al escalamiento: hace falta el permiso
    del módulo dueño *además* de `reports.escalar`. Una demo donde el
    protagonista recibe un 403 al abrir su propia cadena enseña lo contrario
    de lo que quiere enseñar — por eso el reparto sigue el RBAC sembrado y no
    al revés.
    """
    guion: list[str] = []

    def reporte_de(codigo: str) -> ReporteEmitido | None:
        return session.scalar(
            select(ReporteEmitido)
            .where(ReporteEmitido.codigo_emision == codigo)
            .order_by(ReporteEmitido.emitido_at.desc())
        )

    # Abierto en el supervisor: nadie lo tocó todavía. Cajero → `sales.leer`.
    demorado = reporte_de("sales.pedido_demorado")
    if demorado is not None:
        escalamientos_uc.abrir(
            session,
            demorado,
            motivo="demora",
            descripcion=(
                "El cliente de la mesa 9 lleva 41 minutos esperando y ya "
                "preguntó dos veces. No puedo apurar cocina desde caja."
            ),
            reportado_por=ctx["cajero"].id,
        )
        guion.append("Escalamiento ABIERTO en supervisor — pedido demorado")

    # Elevado a comercial: el almacenero intentó y no alcanzó. Los dos
    # extremos —almacenero y supervisor— tienen `inventory.leer`, así que la
    # cadena se puede leer en los dos niveles.
    ajuste = reporte_de("inventory.ajuste_fuera_margen")
    if ajuste is not None:
        cadena = escalamientos_uc.abrir(
            session,
            ajuste,
            motivo="error_sistema",
            descripcion=(
                "Faltan 18 unidades y el conteo de ayer cerró cuadrado. "
                "No encuentro el movimiento que las sacó."
            ),
            reportado_por=ctx["almacenero"].id,
        )
        escalamientos_uc.registrar_accion(
            session,
            cadena,
            descripcion="Revisé las salidas de la semana. Ninguna las explica.",
            usuario_id=ctx["supervisor"].id,
        )
        escalamientos_uc.elevar(
            session,
            cadena,
            ajuste,
            descripcion=(
                "Necesito que Comercial decida si se aprueba el ajuste o se "
                "abre una auditoría de almacén."
            ),
            usuario_id=ctx["almacenero"].id,
        )
        guion.append("Escalamiento ELEVADO a comercial — ajuste sin explicación")

    # Resuelto: para que el histórico no esté vacío. Lo cierra el jefe de
    # cocina, que es quien redacta la acción tomada (RN-PRD-014).
    produccion = reporte_de("production.no_conformidad_detectada")
    if produccion is not None:
        # RN-PRD-015: la tanda terminó en desecho, así que el escalamiento no
        # se abre sin el video de la destrucción. Es la regla haciendo su
        # trabajo, y por eso la demo carga el archivo en vez de esquivarla.
        evidencia = Archivo(
            nombre="destruccion-tanda-118",
            extension="mp4",
            mime_type="video/mp4",
            tamano_bytes=18_400_000,
            url_storage="https://demo.local/evidencia/tanda-118.mp4",
            origen="subido",
            entidad_tipo="orden_produccion",
            entidad_id=ctx["orden_produccion"].id,
            subido_por=ctx["jefe_cocina"].id,
        )
        session.add(evidencia)
        session.flush()
        cadena = escalamientos_uc.abrir(
            session,
            produccion,
            motivo="no_conformidad_calidad",
            descripcion="Tanda entera ácida. Se desechó con video de respaldo.",
            reportado_por=ctx["jefe_cocina"].id,
            evidencia_id=evidencia.id,
        )
        escalamientos_uc.resolver(
            session,
            cadena,
            produccion,
            descripcion=(
                "Se corrigió el tiempo de fermentación en la ficha y se "
                "capacitó al turno noche. Sin reincidencia en 3 tandas."
            ),
            usuario_id=ctx["jefe_cocina"].id,
        )
        guion.append("Escalamiento RESUELTO — no conformidad de producción")

    session.commit()
    return guion


def sembrar(session: Session) -> None:
    empresa = session.scalar(select(Empresa))
    sucursal = session.scalar(select(Sucursal).order_by(Sucursal.nombre))
    almacen = session.scalar(select(Almacen).where(Almacen.empresa_id == empresa.id))
    punto = session.scalar(select(PuntoVenta))
    if not (empresa and sucursal and almacen and punto):
        raise SystemExit(
            "Corre primero `python -m src.seeders.seed` y "
            "`python -m src.seeders.pdv_demo`."
        )

    borrados = borrar_lo_viejo(session)
    print(
        f"Borrados: {borrados['reportes']} reportes, "
        f"{borrados['escalamientos']} escalamientos, "
        f"{borrados['notificaciones']} notificaciones, "
        f"{borrados['hechos']} hechos de la corrida anterior."
    )

    equipo = {
        username: _usuario(session, username, rol, display, sucursal)
        for username, rol, display in EQUIPO
    }
    session.commit()

    ctx = {
        "empresa": empresa,
        "sucursal": sucursal,
        "almacen": almacen,
        "punto": punto,
        "sku": _sku_demo(session, empresa),
        "almacenero": equipo["almacenero1"],
        "cajero": equipo["cajero1"],
        "supervisor": equipo["supervisor1"],
        "jefe_cocina": equipo["jefecocina1"],
        "contador": equipo["contador1"],
    }

    guion = sembrar_situaciones(session, ctx)
    guion += sembrar_escalamientos(session, ctx)

    emitidos = len(list(session.scalars(select(ReporteEmitido.id))))
    entregas = len(list(session.scalars(select(EntregaReporte.id))))
    print(f"\n{emitidos} reportes emitidos, {entregas} entregas:")
    for linea in guion:
        print(f"  · {linea}")

    # Qué va a ver cada uno, contado de verdad. Sin esto hay que adivinar con
    # quién entrar, y una bandeja vacía parece un error cuando es la regla:
    # el que provoca un hecho no se autonotifica.
    print(f"\nBandeja de cada uno (PIN {PIN_DEMO}):")
    for username, _rol, display in EQUIPO:
        usuario = equipo[username]
        cuantos = len(
            list(
                session.scalars(
                    select(EntregaReporte.id).where(
                        EntregaReporte.usuario_id == usuario.id
                    )
                )
            )
        )
        print(f"  {username:<13} {display:<15} {cuantos} reporte(s)")
    print("  admin         (comodín)      todos, en Reportes → Emitidos")


def main() -> None:
    if settings.environment == "production":
        sys.exit("El seeder de demo no corre en producción.")
    # Solo estos dos: publicar los eventos con los listeners de inventory o
    # accounting registrados dispararía asientos y movimientos de stock que
    # esta demo no quiere: acá el hecho ya está puesto a mano.
    reports_listeners.register()
    users_listeners.register()
    with SessionLocal() as session:
        sembrar(session)


if __name__ == "__main__":
    main()
