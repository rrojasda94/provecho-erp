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
from src.modules.sales.application.errors import (
    Conflicto,
    NoEncontrado,
    ReglaNegocio,
    SalesError,
)
from src.modules.sales.application.scope import exigir_venta
from src.modules.sales.domain import rules
from src.modules.sales.infrastructure.repositories import (
    ComprobanteRepo,
    PuntoVentaRepo,
    VentaRepo,
)
from src.modules.users.api.deps import get_db, get_tenant, require_permission
from src.modules.users.application import autorizacion
from src.modules.users.application.errors import TokenInvalido
from src.modules.users.infrastructure.models import Usuario
from src.shared.integrations.factiliza import FactilizaError

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

_HTTP_STATUS: dict[type[SalesError], int] = {
    NoEncontrado: status.HTTP_404_NOT_FOUND,
    Conflicto: status.HTTP_409_CONFLICT,
    ReglaNegocio: status.HTTP_409_CONFLICT,
}


def _http(err: SalesError) -> HTTPException:
    # Por isinstance y no por `type`: un error derivado (PrecioNoDefinido de
    # ReglaNegocio) debe heredar el estado de su base, no caer al 400 genérico.
    for tipo, codigo in _HTTP_STATUS.items():
        if isinstance(err, tipo):
            return HTTPException(codigo, str(err))
    return HTTPException(400, str(err))


# --- Venta ------------------------------------------------------------------
@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    body: schemas.VentaCreate,
    actor: Usuario = Depends(require_permission(CREAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    tenant.exigir_sucursal(body.sucursal_id)
    try:
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
    except (NoEncontrado, ReglaNegocio, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return venta


@router.get("/ventas", response_model=list[schemas.VentaOut])
def listar_ventas_del_dia(
    sucursal_id: uuid.UUID,
    fecha: date | None = None,
    estado: str | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Jornada de una sucursal. Alimenta la pestaña de cobrados del PDV:
    verificar lo vendido y reimprimir un comprobante que el cliente perdió.
    """
    tenant.exigir_sucursal(sucursal_id)
    return VentaRepo(session).del_dia(
        sucursal_id=sucursal_id,
        fecha=fecha or date.today(),
        estados=(estado,) if estado else None,
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
        exigir_venta(session, venta_id, tenant)
        venta = ventas.aplicar_descuento(
            session,
            venta_id=venta_id,
            modo=body.modo,
            valor=body.valor,
            motivo=body.motivo,
            autorizado_por=autorizado_por,
        )
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except (NoEncontrado, ReglaNegocio, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return venta


@router.get("/ventas/{venta_id}", response_model=schemas.VentaOut)
def ver_venta(
    venta_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        return exigir_venta(session, venta_id, tenant)
    except NoEncontrado as e:
        raise _http(e) from e


@router.post("/ventas/{venta_id}/pagos", response_model=schemas.PagoOut, status_code=201)
def registrar_pago(
    venta_id: uuid.UUID,
    body: schemas.PagoCreate,
    _: Usuario = Depends(require_permission(COBRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
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
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
        exigir_venta(session, venta_id, tenant)
        venta = ventas.anular_lineas(
            session,
            venta_id=venta_id,
            venta_item_ids=body.venta_item_ids,
            autorizado_por=autorizado_por,
            motivo=body.motivo,
        )
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    try:
        exigir_venta(session, venta_id, tenant)
        return precuenta.generar(session, venta_id, grupo_cobro)
    except NoEncontrado as e:
        raise _http(e) from e


@router.post("/ventas/{venta_id}/anular", response_model=schemas.VentaOut)
def anular_venta(
    venta_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ANULAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    try:
        exigir_venta(session, venta_id, tenant)
        venta = ventas.anular_venta(session, venta_id, actor.id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
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
    try:
        exigir_venta(session, venta_id, tenant)
        resultado = cumplimiento.registrar_entrega(
            session, venta_id, entregado_por=actor.id
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    except FactilizaError as e:
        session.commit()  # conserva el intento contado
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
    try:
        prod = catalogo.crear_producto(session, **body.model_dump())
    except Conflicto as e:
        raise _http(e) from e
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
    try:
        vinculo = catalogo.vincular_extra(
            session,
            producto_id=producto_id,
            extra_id=body.extra_id,
            maximo=body.maximo,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
    session.commit()
    return {
        "producto_comercial_id": str(vinculo.producto_comercial_id),
        "extra_id": str(vinculo.extra_id),
        "maximo": vinculo.maximo,
    }


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
    try:
        prod = catalogo.editar_producto(session, producto_id, **body.model_dump())
    except NoEncontrado as e:
        raise _http(e) from e
    session.commit()
    return prod


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
    try:
        lista = precios.crear_lista(session, **body.model_dump())
    except Conflicto as e:
        raise _http(e) from e
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
    try:
        precio = precios.fijar_precio(
            session,
            lista_precio_id=lista_id,
            producto_comercial_id=body.producto_comercial_id,
            monto=body.monto,
        )
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
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
    try:
        mesa = mesas.crear_mesa(
            session,
            sucursal_id=body.sucursal_id,
            numero=body.numero,
            zona=body.zona,
            capacidad=body.capacidad,
        )
    except (Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    try:
        mesa = mesas.desactivar_mesa(session, mesa_id)
    except (NoEncontrado, Conflicto) as e:
        raise _http(e) from e
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
    try:
        cliente = clientes.crear_cliente(
            session,
            grupo_id=clientes.grupo_de_empresa(session, tenant.empresa()),
            nombre=body.nombre,
            numero_documento=body.numero_documento,
            telefono=body.telefono,
            email=body.email,
            direccion=body.direccion,
            tipo_documento=body.tipo_documento,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
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
    try:
        grupo_id = clientes.grupo_de_empresa(session, tenant.empresa())
    except NoEncontrado as e:
        raise _http(e) from e
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
    try:
        cliente = clientes.actualizar_documento(
            session,
            cliente_id=cliente_id,
            numero_documento=body.numero_documento,
            tipo_documento=body.tipo_documento,
        )
    except (NoEncontrado, Conflicto, ReglaNegocio) as e:
        raise _http(e) from e
    session.commit()
    return cliente
