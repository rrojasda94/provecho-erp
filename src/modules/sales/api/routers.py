"""Routers FastAPI del módulo sales: venta, cobro y catálogo comercial."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.tenant import Tenant
from src.modules.sales.api import schemas
from src.modules.sales.application import (
    catalogo,
    clientes,
    comprobantes,
    cumplimiento,
    mesas,
    precios,
    precuenta,
    queries_publicas,
    tasks,
    ventas,
)
from src.modules.sales.application.scope import exigir_venta
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.repositories import (
    ComprobanteRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.modules.users.api.deps import (
    ContextoPermiso,
    check_permission,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.application import autorizacion
from src.modules.users.application import queries_publicas as usuarios_queries
from src.modules.users.application.errors import TokenInvalido
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
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
GESTIONAR_MESAS = "sales.gestionar_mesas"
LEER_CLIENTES_EXTERNOS = "sales.leer_clientes_externos"
EMITIR = "sales.emitir_comprobante"
ENTREGAR = "sales.entregar_pedido"


# --- Venta ------------------------------------------------------------------
@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    body: schemas.VentaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
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
        mesa_id=body.mesa_id,
        comensales=body.comensales,
        id=body.id,
    )
    session.commit()
    return venta


@router.get("/ventas", response_model=Pagina[schemas.VentaOut])
def listar_ventas_del_dia(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    """Jornada de una sucursal. Alimenta la pestaña de cobrados del PDV:
    verificar lo vendido y reimprimir un comprobante que el cliente perdió.
    """
    tenant.exigir_sucursal(sucursal_id)
    return paginar(
        session,
        VentaRepo(session).q_del_dia(
            sucursal_id=sucursal_id,
            fecha=fecha or fechas.hoy(),
            estados=(estado,) if estado else None,
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
    body: schemas.AnularLineasCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Quita líneas de una orden ya enviada a cocina y repone su insumo.
    Lo pide el cajero, lo autoriza un supervisor con su PIN (RN-COM-020).
    Antes de enviar, el pedido vive en el PDV y no pasa por acá."""
    try:
        autorizado_por = autorizacion.verificar(body.autorizacion, ANULAR)
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    exigir_venta(session, venta_id, tenant)
    venta = ventas.anular_lineas(
        session,
        venta_id=venta_id,
        venta_item_ids=body.venta_item_ids,
        autorizado_por=autorizado_por,
        motivo=body.motivo,
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
    actor: Usuario = Depends(require_permission(ANULAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_venta(session, venta_id, tenant)
    venta = ventas.anular_venta(session, venta_id, actor.id)
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
    salida = []
    for cliente, persona in clientes.buscar(session, grupo_id=grupo_id, q=q):
        es_juridico = cliente.tipo == "juridico"
        doc = cliente.ruc if es_juridico else (persona.numero_documento if persona else None)
        salida.append(
            schemas.ClienteBuscadoOut(
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
            )
        )
    return salida


@router.patch("/clientes/{cliente_id}/documento", response_model=schemas.ClienteOut)
def actualizar_documento_cliente(
    cliente_id: uuid.UUID,
    body: schemas.ClienteDocumentoUpdate,
    _: Usuario = Depends(require_permission(CREAR)),
    session: Session = Depends(get_db),
):
    """Completa el documento de un cliente que se registró solo por
    teléfono. Desde ese momento cuenta como identificado para promociones
    (RN-PTS-002)."""
    cliente = clientes.actualizar_documento(
        session,
        cliente_id=cliente_id,
        numero_documento=body.numero_documento,
        tipo_documento=body.tipo_documento,
    )
    session.commit()
    return cliente
