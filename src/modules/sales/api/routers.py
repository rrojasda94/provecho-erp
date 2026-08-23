"""Routers FastAPI del módulo sales: venta, cobro y catálogo comercial."""

import uuid
from datetime import date
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.rate_limit import consumir, ip_de
from src.core.tenant import Tenant
from src.modules.sales.api import schemas
from src.modules.sales.application import (
    catalogo,
    clientes,
    comprobantes,
    cumplimiento,
    importacion_clientes,
    mesas,
    notas_credito,
    precios,
    precuenta,
    queries_publicas,
    tarifa_delivery,
    tasks,
    ventas,
)
from src.modules.sales.application.scope import exigir_cliente, exigir_venta
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.repositories import (
    ComprobanteRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.modules.users.api.deps import (
    ContextoPermiso,
    check_permission,
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.application import autorizacion
from src.modules.users.application import queries_publicas as usuarios_queries
from src.modules.users.application.errors import TokenInvalido
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas, planilla
from src.shared.integrations.factiliza import FactilizaError
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/sales", tags=["sales"])

CREAR = "sales.crear"
COBRAR = "sales.cobrar"
LEER = "sales.leer"
ANULAR = "sales.anular"
CATALOGO = "sales.gestionar_catalogo"
# Aplicar descuento es acto de supervisor: separado de `sales.cobrar` para
# que el cajero no se autorice a sí mismo (RN-COM-017).
DESCONTAR = "sales.aplicar_descuento"
# La comida del personal es costo que sale del inventario sin cobro: la firma
# un encargado, igual que un descuento (RN-COM-025).
CONSUMO_PERSONAL = "sales.registrar_consumo_personal"
GESTIONAR_MESAS = "sales.gestionar_mesas"
LEER_CLIENTES_EXTERNOS = "sales.leer_clientes_externos"
# Administrar el padron del grupo no es el mismo acto que registrar a
# alguien en el mostrador, que es lo que hace el cajero con `sales.crear`.
GESTIONAR_CLIENTES = "sales.gestionar_clientes"
EMITIR = "sales.emitir_comprobante"
# Acreditar una venta cobrada devuelve plata: permiso propio, no el del
# cajero que emitió (RN-CPP-009).
NOTA_CREDITO = "sales.emitir_nota_credito"
ENTREGAR = "sales.entregar_pedido"


def _xlsx(contenido: bytes, nombre: str) -> Response:
    """Una planilla como descarga. El `Content-Disposition` es lo que le da
    nombre al archivo en el navegador."""
    return Response(
        content=contenido,
        media_type=planilla.MIME,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )



# --- Venta ------------------------------------------------------------------
@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    body: schemas.VentaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Confirma la orden y la manda a cocina.

    `tipo="consumo_personal"` (RN-COM-025) es la comida del personal: el
    cajero la arma con su permiso `sales.crear`, pero la **autoriza un
    encargado** con su PIN en el mismo terminal — el id de quien firma sale
    del token de `POST /auth/autorizar`, nunca del cuerpo (RN-AUD-005).
    """
    tenant.exigir_sucursal(body.sucursal_id)
    autorizado_por = None
    if rules.es_consumo_personal(body.tipo):
        if not body.autorizacion:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "el consumo de personal requiere autorización de un encargado",
            )
        try:
            autorizado_por = autorizacion.verificar(body.autorizacion, CONSUMO_PERSONAL)
        except TokenInvalido as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    venta = ventas.crear_venta(
        session,
        sucursal_id=body.sucursal_id,
        punto_venta_id=body.punto_venta_id,
        canal=body.canal,
        modalidad=body.modalidad,
        usuario_id=actor.id,
        idempotency_key=body.idempotency_key,
        items=[it.model_dump() for it in body.items],
        cliente_id=body.cliente_id,
        referencia_atencion=body.referencia_atencion,
        direccion_entrega=body.direccion_entrega,
        ubicacion_place_id=body.ubicacion_place_id,
        ubicacion_lat=body.ubicacion_lat,
        ubicacion_lng=body.ubicacion_lng,
        ubicacion_plus_code=body.ubicacion_plus_code,
        ubicacion_distrito=body.ubicacion_distrito,
        mesa_id=body.mesa_id,
        comensales=body.comensales,
        id=body.id,
        tipo=body.tipo,
        consumo_motivo=body.consumo_motivo,
        consumo_autorizado_por=autorizado_por,
    )
    session.commit()
    return venta


@router.post("/ventas/cotizar-delivery", response_model=schemas.CotizacionDeliveryOut)
def cotizar_delivery(
    body: schemas.CotizacionDeliveryIn,
    request: Request,
    actor: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    """Cuánto sale llevar este pedido, y si conviene derivarlo (ADR-054).

    **Con cuota, como la consulta de documento**: cada llamada gasta una
    medición de un proveedor pago, y un bucle mal escrito en el PDV se come
    el plan del mes. Se cuenta por usuario y por IP por la misma razón que
    en `core/consulta_router.py` — todas las cajas del local salen por la
    misma IP, y limitar solo por ahí castiga al equipo por uno solo.

    No decide nada: el precio que se cobra lo vuelve a calcular el servidor
    al crear la venta, y es el que queda congelado en la fila. Esto es lo que
    el cajero ve antes de aceptar.
    """
    ventana = settings.consulta_documento_ventana_segundos
    consumir(
        "cotizar_delivery_usuario",
        str(actor.id),
        settings.consulta_documento_intentos_usuario,
        ventana,
    )
    consumir(
        "cotizar_delivery_ip",
        ip_de(request),
        settings.consulta_documento_intentos_ip,
        ventana,
    )
    cotizacion = tarifa_delivery.cotizar(
        tarifa_delivery.origen_de_sucursal(session, body.sucursal_id),
        tarifa_delivery.coordenada(body.ubicacion_lat, body.ubicacion_lng),
        body.ubicacion_distrito,
    )
    return schemas.CotizacionDeliveryOut(
        distancia_km=cotizacion.distancia_km,
        costo=cotizacion.costo,
        aproximada=cotizacion.aproximada,
        derivar_a_externo=cotizacion.derivar_a_externo,
        motivo=cotizacion.motivo,
    )


@router.get("/ventas", response_model=Pagina[schemas.VentaOut])
def listar_ventas(
    sucursal_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    punto_venta_id: uuid.UUID | None = None,
    tipo: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Ventas del alcance del usuario, filtrables por sucursal, rango de
    fechas, estado y punto de venta.

    Los defaults son la jornada de hoy en las sucursales del usuario: así el
    PDV pide su pestaña de cobrados sin parámetros de fecha y el back-office
    pide un histórico con `desde`/`hasta` (ambos inclusivos) por el mismo
    endpoint, en vez de tener uno para cada uso.
    """
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
        sucursales: list[uuid.UUID] | None = [sucursal_id]
    elif tenant.superusuario:
        # Mismo criterio que `Tenant.exigir_sucursal`, que ya lo deja pasar a
        # cualquier sucursal: al superusuario no se le recorta el alcance, o
        # el listado sin filtro mostraría menos que el listado con filtro.
        sucursales = None
    else:
        sucursales = list(tenant.sucursal_ids)

    desde = desde or fechas.hoy()
    hasta = hasta or desde
    if hasta < desde:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "`hasta` no puede ser anterior a `desde`"
        )
    return paginar(
        session,
        VentaRepo(session).q_listar(
            sucursal_ids=sucursales,
            desde=desde,
            hasta=hasta,
            estados=(estado,) if estado else None,
            punto_venta_id=punto_venta_id,
            tipo=tipo,
        ),
        p,
    )


@router.post("/ventas/{venta_id}/descuento", response_model=schemas.VentaOut)
def aplicar_descuento(
    venta_id: uuid.UUID,
    body: schemas.DescuentoCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Lo **pide** el cajero (permiso `sales.cobrar`) y lo **autoriza** un
    supervisor con su PIN en el mismo terminal: la elevación de
    `POST /auth/autorizar` viaja en `autorizacion` y de ahí sale
    `autorizado_por` (RN-COM-017, RN-AUD-005).
    """
    try:
        autorizado_por = autorizacion.verificar(body.autorizacion, DESCONTAR)
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    venta = exigir_venta(session, venta_id, tenant)
    # Tope de `permiso.restricciones` para quien autorizó (ADR-023): un rol
    # puede tener `sales.aplicar_descuento` con `monto_maximo` — no todo
    # supervisor autoriza cualquier monto. Solo aplica al dar un descuento
    # nuevo, no al quitarlo (`modo=None`); se valida ANTES de comprometer
    # el cambio, no después.
    if body.modo is not None:
        autorizante = usuarios_queries.obtener_usuario(session, autorizado_por)
        monto = ventas.calcular_monto_descuento(session, venta, body.modo, body.valor)
        check_permission(
            session, autorizante, DESCONTAR, contexto=ContextoPermiso(monto=monto)
        )
    venta = ventas.aplicar_descuento(
        session,
        venta_id=venta_id,
        modo=body.modo,
        valor=body.valor,
        motivo=body.motivo,
        autorizado_por=autorizado_por,
    )
    session.commit()
    return venta


@router.get("/ventas/{venta_id}", response_model=schemas.VentaOut)
def ver_venta(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_venta(session, venta_id, tenant)


@router.get("/ventas/{venta_id}/items", response_model=list[schemas.VentaItemOut])
def ver_items_venta(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Líneas de una venta ya confirmada: reabrir una mesa en curso en el
    PDV, o elegir qué anular, necesitan verlas con su id real (RN-COM-020)."""
    exigir_venta(session, venta_id, tenant)
    return ventas.listar_items(session, venta_id)


@router.post("/ventas/{venta_id}/pagos", response_model=schemas.PagoOut, status_code=201)
def registrar_pago(
    venta_id: uuid.UUID,
    body: schemas.PagoCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    pago, _venta, comprobante = ventas.registrar_pago(
        session,
        venta_id=venta_id,
        medio_pago_id=body.medio_pago_id,
        monto=body.monto,
        idempotency_key=body.idempotency_key,
        referencia_externa=body.referencia_externa,
        grupo_cobro=body.grupo_cobro,
        receptor_num_doc=body.receptor_num_doc,
        receptor_nombre=body.receptor_nombre,
        id=body.id,
    )
    session.commit()
    # Después del commit: el worker corre en otro proceso y solo puede ver
    # filas ya confirmadas.
    if comprobante is not None:
        tasks.encolar(comprobante.id)
    return pago


@router.post("/ventas/{venta_id}/anular-lineas", response_model=schemas.VentaOut)
def anular_lineas(
    venta_id: uuid.UUID,
    body: schemas.AnularLineasCreate | None = None,
    actor: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Quita líneas de una orden ya enviada a cocina y repone su insumo.

    **Dentro de los 5 minutos** de haberse enviado la línea, la quita el
    cajero solo: es corregir un tecleo, el plato todavía no se armó
    (RN-COM-029). Pasada la ventana el insumo ya se usó de verdad y hace
    falta la firma de un supervisor (RN-COM-020) — la pide el cajero y la da
    el supervisor con su PIN en el mismo terminal.

    Antes de enviar, el pedido vive en el PDV y no pasa por acá.
    """
    if body is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "indica las líneas a anular"
        )
    exigir_venta(session, venta_id, tenant)
    autorizado_por = actor.id
    if not ventas.lineas_en_ventana(session, venta_id, body.venta_item_ids):
        if not body.autorizacion:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "pasaron más de "
                f"{int(rules.VENTANA_CORRECCION.total_seconds() // 60)} minutos: "
                "quitar la línea lo autoriza un supervisor con su PIN",
            )
        try:
            autorizado_por = autorizacion.verificar(body.autorizacion, ANULAR)
        except TokenInvalido as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    venta = ventas.anular_lineas(
        session,
        venta_id=venta_id,
        venta_item_ids=body.venta_item_ids,
        autorizado_por=autorizado_por,
        motivo=body.motivo,
    )
    session.commit()
    return venta


@router.post("/ventas/{venta_id}/items", response_model=schemas.VentaOut, status_code=201)
def agregar_lineas(
    venta_id: uuid.UUID,
    body: schemas.AgregarLineasCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Suma líneas a una orden ya enviada a cocina (RN-COM-029).

    Sin autorización de nadie y con el mismo permiso que crear la orden:
    agregar es lo que el negocio quiere que pase. Una mesa pide de a poco, y
    obligar a abrir una orden nueva para la segunda ronda termina en dos
    cuentas y dos entregas para la misma mesa. Lo que sigue necesitando firma
    —después de la ventana— es **quitar**, porque repone inventario.
    """
    exigir_venta(session, venta_id, tenant)
    venta = ventas.agregar_lineas(
        session,
        venta_id=venta_id,
        items=[it.model_dump() for it in body.items],
        usuario_id=actor.id,
    )
    session.commit()
    return venta


@router.get("/ventas/{venta_id}/precuenta", response_model=schemas.PrecuentaOut)
def ver_precuenta(
    venta_id: uuid.UUID,
    grupo_cobro: int | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Documento **no fiscal** para que el cliente revise su consumo antes
    de pagar (RN-COM-019). No cambia el estado de la venta ni se audita:
    pedirla dos veces es normal."""
    exigir_venta(session, venta_id, tenant)
    return precuenta.generar(session, venta_id, grupo_cobro)


@router.post("/ventas/{venta_id}/anular", response_model=schemas.VentaOut)
def anular_venta(
    venta_id: uuid.UUID,
    body: schemas.AnularVentaIn | None = None,
    actor: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Anula una orden no pagada. Post-pago es nota de crédito.

    Entra quien opera la caja (`sales.cobrar`) **o** quien puede anular
    (`sales.anular`) — son dos roles distintos y ninguno es subconjunto del
    otro: el `cajero` cobra y no anula, el `supervisor` anula y no cobra.
    Exigir los dos habría dejado afuera a los dos.

    Al que solo cobra le hace falta además la firma de alguien que sí pueda,
    igual que para quitar una línea ya enviada (RN-COM-020): el cajero pide y
    el supervisor autoriza con su PIN en el mismo terminal.

    Antes exigía `sales.anular` a secas, que el rol `cajero` no tiene: el
    botón "Anular pedido" del PDV devolvía 403 sin decir qué hacer, y el
    pedido quedaba en cocina.
    """
    check_permission(session, actor, COBRAR, ANULAR)
    exigir_venta(session, venta_id, tenant)
    quien_autoriza = actor.id
    # Dentro de la ventana de corrección alcanza con quien opera la caja
    # (RN-COM-029): la comanda acaba de salir y el plato todavía no se armó.
    puede_solo = usuarios_queries.tiene_permiso(
        session, actor.id, ANULAR
    ) or ventas.venta_en_ventana(session, venta_id)
    if not puede_solo:
        if body is None or not body.autorizacion:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "pasaron más de "
                f"{int(rules.VENTANA_CORRECCION.total_seconds() // 60)} minutos: "
                "anular la orden lo autoriza un supervisor con su PIN",
            )
        try:
            quien_autoriza = autorizacion.verificar(body.autorizacion, ANULAR)
        except TokenInvalido as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    # Queda firmada por quien la autorizó, no por quien la tecleó: es lo que
    # el `audit_log` tiene que poder responder cuando alguien pregunta quién
    # dejó sin cobrar esa orden.
    venta = ventas.anular_venta(session, venta_id, quien_autoriza)
    session.commit()
    return venta


# --- Cumplimiento de pedido (PROC-OPE-002) ----------------------------------
@router.post("/ventas/{venta_id}/entrega", response_model=schemas.EntregaOut)
def registrar_entrega(
    venta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ENTREGAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cierra el pedido: lo entrega al cliente y publica
    `sales.venta_entregada`. Permiso propio, distinto del avance de cocina
    (RN-CUP-006); repetirlo no reemite el evento (RN-CUP-005)."""
    exigir_venta(session, venta_id, tenant)
    resultado = cumplimiento.registrar_entrega(
        session, venta_id, entregado_por=actor.id
    )
    session.commit()
    return resultado


# --- Comprobante electrónico ------------------------------------------------
@router.get("/ventas/{venta_id}/comprobante", response_model=schemas.ComprobanteOut)
def ver_comprobante(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    comprobante = ComprobanteRepo(session).por_venta(venta_id)
    if comprobante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "la venta no tiene comprobante")
    return comprobante


@router.post(
    "/comprobantes/{comprobante_id}/reintentar",
    response_model=schemas.ComprobanteOut,
)


def reintentar_emision(
    comprobante_id: uuid.UUID,
    _: Usuario = Depends(require_permission(EMITIR)),
    session: Session = Depends(get_db),
):
    """Reenvía a SUNAT un comprobante rechazado o con fallo de transporte.
    Corre en línea (no en la cola) para devolver el veredicto al operador."""
    try:
        comprobante = comprobantes.emitir_comprobante(session, comprobante_id)
    except FactilizaError as e:
        # Commit en el camino de error: el intento ya quedó contado en la
        # fila y hay que persistirlo. Por eso este `except` sobrevive al
        # handler global — no solo traduce, decide sobre la transacción.
        session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    session.commit()
    return comprobante


@router.get(
    "/comprobantes/{comprobante_id}/descargar/{formato}", response_class=Response
)
def descargar_comprobante(
    comprobante_id: uuid.UUID,
    formato: Literal["pdf", "xml", "cdr"],
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Baja el PDF que se entrega al cliente, o el XML firmado y el CDR que
    son el respaldo ante SUNAT.

    Se piden a Factiliza en el momento y no se archivan: su copia es la
    buena mientras el proveedor siga activo. Devuelve los bytes tal cual —
    reescribir un XML firmado lo invalida.
    """
    try:
        documento = comprobantes.descargar_documento(session, comprobante_id, formato)
    except FactilizaError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return Response(
        content=documento.contenido,
        media_type=documento.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{documento.nombre_archivo}"'
        },
    )


@router.post(
    "/comprobantes/{comprobante_id}/nota-credito",
    response_model=schemas.ComprobanteOut,
    status_code=201,
)
def emitir_nota_credito(
    comprobante_id: uuid.UUID,
    body: schemas.NotaCreditoCreate,
    actor: Usuario = Depends(require_permission(NOTA_CREDITO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Corrige una venta ya cobrada (RN-CPP-009). Permiso propio: acreditar
    devuelve plata y no es acto de cajero.

    Sin `detalle` la nota es total; con `detalle` acredita solo esas líneas.
    `repone_stock` lo decide quien emite — un plato devuelto en cocina rara
    vez devuelve el insumo, y corregir el RUC de una factura no toca el
    inventario.
    """
    comprobante = ComprobanteRepo(session).get(comprobante_id)
    if comprobante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comprobante no encontrado")
    if comprobante.venta_id is not None:
        exigir_venta(session, comprobante.venta_id, tenant)
    try:
        nota = notas_credito.emitir_nota_credito(
            session,
            comprobante_id,
            motivo=body.motivo,
            emitido_por=actor.id,
            detalle=[d.model_dump() for d in body.detalle] if body.detalle else None,
            repone_stock=body.repone_stock,
            motivo_descripcion=body.motivo_descripcion,
        )
    except FactilizaError as e:
        # Igual que al reintentar: el intento ya quedó contado en la fila y
        # hay que persistirlo, así que este `except` decide sobre la
        # transacción además de traducir.
        session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    session.commit()
    return nota


# --- Contrato público de lectura (marketing/comercial/análisis) -------------
@router.get("/clientes", response_model=list[schemas.ClientePublicoOut])
def listar_clientes_publico(
    grupo_id: uuid.UUID,
    tipo: str | None = None,
    _: Usuario = Depends(require_permission(LEER_CLIENTES_EXTERNOS)),
    session: Session = Depends(get_db),
):
    return queries_publicas.listar_clientes_para_analisis(session, grupo_id, tipo=tipo)


# --- Catálogo comercial -----------------------------------------------------
@router.post("/productos", response_model=schemas.ProductoOut, status_code=201)
def crear_producto(
    body: schemas.ProductoCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    prod = catalogo.crear_producto(session, **body.model_dump())
    session.commit()
    return prod


@router.post("/productos/{producto_id}/extras", status_code=201)
def vincular_extra(
    producto_id: uuid.UUID,
    body: schemas.VincularExtraCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Habilita un extra sobre un producto. Ambas puntas son
    `producto_comercial`: el extra es uno con `es_extra=True` y su propia
    receta, que se suma a la del producto al agregarse (RN-COM-021)."""
    vinculo = catalogo.vincular_extra(
        session,
        producto_id=producto_id,
        extra_id=body.extra_id,
        maximo=body.maximo,
        grupo_id=body.grupo_id,
    )
    session.commit()
    return {
        "producto_comercial_id": str(vinculo.producto_comercial_id),
        "extra_id": str(vinculo.extra_id),
        "maximo": vinculo.maximo,
        "grupo_id": str(vinculo.grupo_id) if vinculo.grupo_id else None,
    }


@router.get("/productos/{producto_id}/quitables", response_model=list[schemas.QuitableOut])
def quitables(
    producto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Insumos que este producto admite quitar ("sin cebolla", RN-PRD-004).
    Es la receta del producto: no hay una lista aparte que mantener."""
    return catalogo.quitables_de(session, producto_id)


@router.delete("/productos/{producto_id}/extras/{extra_id}", status_code=204)
def desvincular_extra(
    producto_id: uuid.UUID,
    extra_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Deja de ofrecer el extra en este producto. El extra sigue existiendo:
    es un producto comercial con su receta y su precio."""
    catalogo.desvincular_extra(session, producto_id=producto_id, extra_id=extra_id)
    session.commit()


@router.post("/productos/{producto_id}/grupos", response_model=schemas.GrupoOpcionOut,
             status_code=201)
def crear_grupo_opcion(
    producto_id: uuid.UUID,
    body: schemas.GrupoOpcionCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Agrupa extras y define cuántos hay que elegir. `minimo >= 1` hace el
    grupo obligatorio en el PDV (RN-COM-023)."""
    grupo = catalogo.crear_grupo_opcion(session, producto_id=producto_id, **body.model_dump())
    session.commit()
    return {
        "id": grupo.id,
        "nombre": grupo.nombre,
        "minimo": grupo.minimo,
        "maximo": grupo.maximo,
        "orden": grupo.orden,
        "extras": [],
    }


@router.delete("/productos/{producto_id}/grupos/{grupo_id}", status_code=204)
def borrar_grupo_opcion(
    producto_id: uuid.UUID,
    grupo_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Borra el grupo. Sus extras quedan sueltos (siguen ofreciéndose, ya
    sin mínimo obligatorio)."""
    catalogo.borrar_grupo_opcion(session, producto_id=producto_id, grupo_id=grupo_id)
    session.commit()


@router.get("/marcas", response_model=list[schemas.MarcaOut])
def listar_marcas(
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Marcas disponibles para colgar un producto. Vive en `sales` y no en
    `users` porque el único consumidor es el catálogo comercial."""
    return catalogo.listar_marcas(session)


@router.get("/productos/{producto_id}", response_model=schemas.ProductoDetalleOut)
def ver_producto(
    producto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    """Ficha completa: el producto, sus variantes y sus grupos de extras."""
    return catalogo.detalle_producto(session, producto_id)


@router.get("/productos", response_model=list[schemas.ProductoOut])
def listar_productos(
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return catalogo.listar_productos(session, marca_id)


@router.patch("/productos/{producto_id}", response_model=schemas.ProductoOut)
def editar_producto(
    producto_id: uuid.UUID,
    body: schemas.ProductoUpdate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    prod = catalogo.editar_producto(session, producto_id, **body.model_dump())
    session.commit()
    return prod


@router.delete("/productos/{producto_id}", status_code=204)
def eliminar_producto(
    producto_id: uuid.UUID,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Borra un producto que nunca se vendió. Si ya tiene ventas responde 409:
    ahí se descontinúa (`activo=False`), no se borra."""
    catalogo.eliminar_producto(session, producto_id)
    session.commit()


@router.post("/medios-pago", response_model=schemas.MedioPagoOut, status_code=201)
def crear_medio_pago(
    body: schemas.MedioPagoCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    medio = catalogo.crear_medio_pago(session, **campos)
    session.commit()
    return medio


@router.get("/medios-pago", response_model=list[schemas.MedioPagoOut])
def listar_medios_pago(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return catalogo.listar_medios_pago(session, tenant.filtro_empresa(empresa_id))


# --- Precios (server-side, RN-PRC-003) --------------------------------------
@router.post("/listas-precio", response_model=schemas.ListaPrecioOut, status_code=201)
def crear_lista_precio(
    body: schemas.ListaPrecioCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    lista = precios.crear_lista(session, **body.model_dump())
    session.commit()
    return lista


@router.get("/listas-precio", response_model=list[schemas.ListaPrecioOut])
def listar_listas_precio(
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    session: Session = Depends(get_db),
):
    return precios.listar_listas(session, marca_id)


@router.post(
    "/listas-precio/{lista_id}/precios",
    response_model=schemas.PrecioOut,
    status_code=201,
)


def fijar_precio(
    lista_id: uuid.UUID,
    body: schemas.PrecioCreate,
    _: Usuario = Depends(require_permission(CATALOGO)),
    session: Session = Depends(get_db),
):
    """Alta de precio en una lista. No hay PATCH: corregir un precio es una
    lista nueva, para que el histórico quede auditable (RN-PRC-005)."""
    precio = precios.fijar_precio(
        session,
        lista_precio_id=lista_id,
        producto_comercial_id=body.producto_comercial_id,
        monto=body.monto,
    )
    session.commit()
    return precio


@router.get("/carta", response_model=list[schemas.CartaItemOut])
def carta(
    sucursal_id: uuid.UUID,
    canal: str,
    modalidad: str,
    marca_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Catálogo vendible con el precio ya resuelto — lo que el PDV renderiza
    en vez de traer un precio propio."""
    tenant.exigir_sucursal(sucursal_id)
    return precios.carta(
        session,
        sucursal_id=sucursal_id,
        canal=canal,
        modalidad=modalidad,
        marca_id=marca_id,
    )


@router.get("/puntos-venta", response_model=list[schemas.PuntoVentaOut])
def listar_puntos_venta(
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Las cajas de la sucursal. El PDV lo necesita al arrancar: sin saber
    qué punto de venta es, no puede abrir caja ni emitir con la serie
    correcta."""
    tenant.exigir_sucursal(sucursal_id)
    return PuntoVentaRepo(session).de_sucursal(sucursal_id)


# --- Mesas del salón --------------------------------------------------------
@router.post("/mesas", response_model=schemas.MesaOut, status_code=201)
def crear_mesa(
    body: schemas.MesaCreate,
    _: Usuario = Depends(require_permission(GESTIONAR_MESAS)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    mesa = mesas.crear_mesa(
        session,
        sucursal_id=body.sucursal_id,
        numero=body.numero,
        zona=body.zona,
        capacidad=body.capacidad,
    )
    session.commit()
    return mesa


@router.get("/mesas", response_model=list[schemas.MesaOut])
def listar_mesas(
    sucursal_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(sucursal_id)
    return mesas.listar_mesas(session, sucursal_id)


@router.get("/mesas/mapa", response_model=list[schemas.MesaEnMapaOut])
def mapa_de_mesas(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Estado del salón: qué mesa está ocupada, con qué orden y por cuánto.
    Derivado de las ventas en `orden` — la mesa no guarda estado propio."""
    tenant.exigir_sucursal(sucursal_id)
    return [
        schemas.MesaEnMapaOut(
            id=m.mesa.id,
            numero=m.mesa.numero,
            zona=m.mesa.zona,
            capacidad=m.mesa.capacidad,
            venta_id=m.venta_id,
            numero_orden=m.numero_orden,
            comensales=m.comensales,
            total=m.total,
        )
        for m in mesas.mapa(session, sucursal_id=sucursal_id, fecha=fecha)
    ]


@router.post("/mesas/{mesa_id}/desactivar", response_model=schemas.MesaOut)
def desactivar_mesa(
    mesa_id: uuid.UUID,
    _: Usuario = Depends(require_permission(GESTIONAR_MESAS)),
    session: Session = Depends(get_db),
):
    mesa = mesas.desactivar_mesa(session, mesa_id)
    session.commit()
    return mesa


# --- Cliente creado desde caja ----------------------------------------------
@router.post("/clientes", response_model=schemas.ClienteOut, status_code=201)
def crear_cliente(
    body: schemas.ClienteCreate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Alta rápida desde el PDV. Registrar es opcional: vender a cliente
    anónimo sigue siendo válido (RN-PER-005). Para una persona natural basta
    el teléfono; para facturar a una empresa el RUC es obligatorio
    (RN-PTS-002)."""
    cliente = clientes.crear_cliente(
        session,
        grupo_id=clientes.grupo_de_empresa(session, tenant.empresa()),
        nombre=body.nombre,
        numero_documento=body.numero_documento,
        telefono=body.telefono,
        email=body.email,
        direccion=body.direccion,
        fecha_nacimiento=body.fecha_nacimiento,
        tipo_documento=body.tipo_documento,
    )
    session.commit()
    return cliente


def _cliente_buscado(cliente, persona) -> schemas.ClienteBuscadoOut:
    """Arma la vista de un cliente juntando lo suyo con lo de su persona.

    Vive acá y no duplicado en cada endpoint porque la caja y el back-office
    tienen que leer al mismo cliente igual: dos armados distintos es cómo un
    natural termina mostrándose con un nombre en una pantalla y con otro en
    la de al lado.
    """
    es_juridico = cliente.tipo == "juridico"
    doc = cliente.ruc if es_juridico else (persona.numero_documento if persona else None)
    return schemas.ClienteBuscadoOut(
        id=cliente.id,
        tipo=cliente.tipo,
        nombre=(
            cliente.razon_social
            if es_juridico
            else f"{persona.nombres} {persona.apellidos}".strip()
            if persona
            else "—"
        ),
        telefono=persona.telefono if persona else None,
        numero_documento=doc,
        direccion=(
            cliente.contacto if es_juridico else (persona.domicilio if persona else None)
        ),
        identificado=(
            bool(cliente.ruc) if es_juridico else rules.cliente_identificado(doc)
        ),
        persona_id=cliente.persona_id,
    )


@router.get("/clientes/buscar", response_model=list[schemas.ClienteBuscadoOut])
def buscar_clientes(
    q: str,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Búsqueda de caja: por teléfono, documento o nombre — lo que el
    cliente recuerde. Distinta de `GET /clientes`, que es el listado para
    análisis externo y usa otro permiso."""
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    return [
        _cliente_buscado(cliente, persona)
        for cliente, persona in clientes.buscar(session, grupo_id=grupo_id, q=q)
    ]


@router.get("/clientes/listado", response_model=Pagina[schemas.ClienteBuscadoOut])
def listar_clientes_backoffice(
    q: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """El padrón de clientes del grupo, para la pantalla de back-office.

    Endpoint propio y no `GET /clientes`: ese es el contrato público de
    análisis (`sales.leer_clientes_externos`, `grupo_id` por query), pensado
    para que marketing lea desde afuera. Pedirle a quien administra el padrón
    de su propio grupo el permiso de lectura externa sería abrirle de paso
    los clientes que no le tocan.

    Tampoco es `/clientes/buscar`: aquella corta en 20 y exige `q` porque en
    caja se busca a alguien concreto; acá se recorre el padrón entero.
    """
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    pagina = paginar(session, clientes.q_listado(session, grupo_id=grupo_id, q=q), p)
    personas = clientes.personas_de(session, pagina["items"])
    return {
        **pagina,
        "items": [
            _cliente_buscado(c, personas.get(c.persona_id)) for c in pagina["items"]
        ],
    }


# Las cuatro rutas literales van **antes** de `/clientes/{cliente_id}`:
# FastAPI resuelve por orden y "plantilla" entraría como un id que no es UUID.
@router.get("/clientes/plantilla")
def descargar_plantilla_clientes(
    _: Usuario = Depends(require_permission(GESTIONAR_CLIENTES)),
):
    """La hoja que se llena para cargar el padrón de golpe (RN-PTS-007)."""
    return _xlsx(importacion_clientes.plantilla(), "plantilla-clientes.xlsx")


@router.get("/clientes/exportar")
def exportar_clientes(
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """El padrón en la misma plantilla, con los datos adentro (ADR-052).

    Pide permiso de **lectura**: son los mismos datos que devuelve el listado
    de back-office, solo empaquetados en un archivo.
    """
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    return _xlsx(
        importacion_clientes.exportar(session, grupo_id=grupo_id), "clientes.xlsx"
    )


@router.post("/clientes/importar/validar", response_model=schemas.RevisionClientesOut)
async def validar_importacion_clientes(
    archivo: UploadFile,
    _: Usuario = Depends(require_permission(GESTIONAR_CLIENTES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Dice qué entra, qué actualiza y qué no. **No guarda nada.**"""
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    return importacion_clientes.validar(
        session, grupo_id=grupo_id, contenido=await archivo.read()
    )


@router.post(
    "/clientes/importar",
    status_code=201,
    response_model=schemas.ResultadoImportacionOut,
)
def importar_clientes(
    body: schemas.ImportarClientesIn,
    _: Usuario = Depends(require_permission(GESTIONAR_CLIENTES)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Crea y actualiza lo que la pantalla confirmó, revalidando todo."""
    grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    resultado = importacion_clientes.importar(
        session,
        grupo_id=grupo_id,
        clientes=[c.model_dump() for c in body.clientes],
    )
    session.commit()
    return resultado


@router.patch("/clientes/{cliente_id}", response_model=schemas.ClienteOut)
def editar_cliente(
    cliente_id: uuid.UUID,
    body: schemas.ClienteUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Corrige razón social, RUC o contacto de un cliente **jurídico**. Un
    RUC mal tecleado llega hasta la factura electrónica y hasta ahora no
    tenía arreglo por API.

    Un cliente natural responde 422: sus datos viven en su `persona`
    (RN-GEN-007) y se corrigen desde `PATCH /personas/{id}`.
    """
    exigir_cliente(session, cliente_id, tenant)
    cliente = clientes.editar_cliente(session, cliente_id, **body.model_dump())
    session.commit()
    return cliente


@router.patch("/clientes/{cliente_id}/documento", response_model=schemas.ClienteOut)
def actualizar_documento_cliente(
    cliente_id: uuid.UUID,
    body: schemas.ClienteDocumentoUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Completa el documento de un cliente que se registró solo por
    teléfono. Desde ese momento cuenta como identificado para promociones
    (RN-PTS-002)."""
    # Faltaba el alcance de tenant: con el `cliente_id` de otro grupo, este
    # endpoint le escribía el documento igual (ADR-004).
    exigir_cliente(session, cliente_id, tenant)
    cliente = clientes.actualizar_documento(
        session,
        cliente_id=cliente_id,
        numero_documento=body.numero_documento,
        tipo_documento=body.tipo_documento,
    )
    session.commit()
    return cliente
