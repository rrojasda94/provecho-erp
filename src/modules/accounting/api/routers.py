"""Routers FastAPI del módulo accounting: plan de cuentas, periodos, asientos
y mapeo de asientos automáticos."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.tenant import Tenant
from src.modules.accounting.api import schemas
from src.modules.accounting.application import (
    asientos,
    caja,
    cuentas,
    estados_financieros,
    pagos,
    periodos,
    reglas,
)
from src.modules.accounting.application import pcge as pcge_uc
from src.modules.accounting.application import pos as pos_uc
from src.modules.accounting.application.scope import (
    exigir_apertura_caja,
    exigir_asiento,
    exigir_cierre_caja,
    exigir_cuenta,
    exigir_custodia,
    exigir_pago,
    exigir_periodo,
    exigir_pos_tarjeta,
    exigir_punto_venta,
)
from src.modules.accounting.infrastructure.repositories import (
    AsientoRepo,
    CustodiaEfectivoRepo,
    MovimientoCajaRepo,
)
from src.modules.users.api.deps import (
    check_permission,
    get_current_user,
    get_db,
    get_tenant,
    require_permission,
)
from src.modules.users.application import autorizacion
from src.modules.users.application.errors import TokenInvalido
from src.modules.users.application.queries_publicas import tiene_permiso
from src.modules.users.infrastructure.models import Usuario
from src.shared import fechas
from src.shared.paginacion import Pagina, Paginacion, paginacion, paginar

router = APIRouter(prefix="/accounting", tags=["accounting"])

CUENTA_ADMINISTRAR = "accounting.cuenta_administrar"
PERIODO_ADMINISTRAR = "accounting.periodo_administrar"
ASIENTO_MANUAL = "accounting.asiento_manual"
LEER = "accounting.leer"
PAGO_GESTIONAR = "accounting.pago_gestionar"
PAGO_APROBAR = "accounting.pago_aprobar"
CAJA_OPERAR = "accounting.caja_operar"
ARQUEO_REGISTRAR = "accounting.arqueo_registrar"
# Retirar efectivo del cajón lo autoriza un supervisor, no el cajero solo
# (RN-MDP-007).
CAJA_RETIRAR = "accounting.caja_retirar"
# Recibir el efectivo en cada tramo de la cadena de custodia (RN-MDP-002):
# del cajón al encargado, del encargado a contabilidad, y de ahí a
# disponible. **Ya no interviene en abrir ni cerrar** (RN-MDP-008, ADR-049):
# el turno lo opera el cajero solo y firmar tiene sentido solo donde la
# plata cambia de manos.
CAJA_RELEVAR = "accounting.caja_relevar"
# Corregir un cierre ya registrado (RN-MDP-005).
CAJA_REABRIR = "accounting.caja_reabrir"
POS_ADMINISTRAR = "accounting.pos_administrar"


def _autorizado(token: str, permiso: str) -> uuid.UUID:
    """Quién firmó con su PIN (`POST /auth/autorizar`), o 403.

    El identificador nunca sale del cuerpo del request: sería una firma
    falsificable y la cadena de custodia dejaría de probar nada.
    """
    try:
        return autorizacion.verificar(token, permiso)
    except TokenInvalido as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e


# --- Plan de cuentas ----------------------------------------------------------
@router.post("/cuentas-contables", response_model=schemas.CuentaContableOut, status_code=201)
def crear_cuenta(
    body: schemas.CuentaContableCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    if campos["cuenta_padre_id"] is not None:
        exigir_cuenta(session, campos["cuenta_padre_id"], tenant)
    cuenta = cuentas.crear_cuenta(session, **campos)
    session.commit()
    return cuenta


@router.get("/cuentas-contables", response_model=list[schemas.CuentaContableOut])
def listar_cuentas(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return cuentas.listar_cuentas(session, tenant.filtro_empresa(empresa_id))


@router.patch("/cuentas-contables/{cuenta_id}", response_model=schemas.CuentaContableOut)
def editar_cuenta(
    cuenta_id: uuid.UUID,
    body: schemas.CuentaContableUpdate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_cuenta(session, cuenta_id, tenant)
    cuenta = cuentas.editar_cuenta(session, cuenta_id, **body.model_dump())
    session.commit()
    return cuenta


# --- Periodo contable ----------------------------------------------------------
@router.post("/periodos", response_model=schemas.PeriodoContableOut, status_code=201)
def abrir_periodo(
    body: schemas.PeriodoContableCreate,
    _: Usuario = Depends(require_permission(PERIODO_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    periodo = periodos.abrir_periodo(session, **campos)
    session.commit()
    return periodo


@router.get("/periodos", response_model=list[schemas.PeriodoContableOut])
def listar_periodos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return periodos.listar_periodos(session, tenant.filtro_empresa(empresa_id))


@router.post("/periodos/{periodo_id}/cerrar", response_model=schemas.PeriodoContableOut)
def cerrar_periodo(
    periodo_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PERIODO_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_periodo(session, periodo_id, tenant)
    periodo = periodos.cerrar_periodo(session, periodo_id, cerrado_por=actor.id)
    session.commit()
    return periodo


# --- Asiento --------------------------------------------------------------------
@router.post("/asientos", response_model=schemas.AsientoOut, status_code=201)
def crear_asiento_manual(
    body: schemas.AsientoManualCreate,
    actor: Usuario = Depends(require_permission(ASIENTO_MANUAL)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    empresa_id = tenant.empresa(body.empresa_id)
    for linea in body.lineas:
        exigir_cuenta(session, linea.cuenta_contable_id, tenant)
    asiento = asientos.crear_asiento_manual(
        session,
        empresa_id=empresa_id,
        fecha=body.fecha,
        glosa=body.glosa,
        lineas=[li.model_dump() for li in body.lineas],
        creado_por=actor.id,
    )
    session.commit()
    return asiento


@router.get("/asientos", response_model=Pagina[schemas.AsientoOut])
def listar_asientos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session, AsientoRepo(session).q_list(tenant.filtro_empresa(empresa_id)), p
    )


@router.get("/asientos/{asiento_id}", response_model=schemas.AsientoOut)
def ver_asiento(
    asiento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return exigir_asiento(session, asiento_id, tenant)


@router.get("/asientos/{asiento_id}/lineas", response_model=list[schemas.AsientoLineaOut])
def ver_lineas_asiento(
    asiento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_asiento(session, asiento_id, tenant)
    return AsientoRepo(session).lineas(asiento_id)


@router.post("/asientos/{asiento_id}/anular", response_model=schemas.AsientoOut)
def anular_asiento(
    asiento_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(ASIENTO_MANUAL)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_asiento(session, asiento_id, tenant)
    reversa = asientos.anular_asiento(session, asiento_id, actor_id=actor.id)
    session.commit()
    return reversa


# --- Regla de asiento (mapeo evento→cuentas) -----------------------------------
@router.post("/reglas-asiento", response_model=schemas.ReglaAsientoOut, status_code=201)
def crear_regla_asiento(
    body: schemas.ReglaAsientoCreate,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    exigir_cuenta(session, campos["cuenta_debe_id"], tenant)
    exigir_cuenta(session, campos["cuenta_haber_id"], tenant)
    regla = reglas.crear_regla_asiento(session, **campos)
    session.commit()
    return regla


@router.get("/reglas-asiento", response_model=list[schemas.ReglaAsientoOut])
def listar_reglas_asiento(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return reglas.listar_reglas_asiento(session, tenant.filtro_empresa(empresa_id))


# --- Pago a proveedor (PROC-CTB-003) --------------------------------------------
@router.post("/pagos-proveedor", response_model=schemas.MovimientoDineroOut, status_code=201)
def registrar_pago(
    body: schemas.PagoProveedorCreate,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    movimiento = pagos.registrar_pago(session, solicitado_por=actor.id, **campos)
    session.commit()
    return movimiento


@router.get("/pagos-proveedor", response_model=Pagina[schemas.MovimientoDineroOut])
def listar_pagos(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    p: Paginacion = Depends(paginacion),
    session: Session = Depends(get_db),
):
    return paginar(
        session, pagos.q_pagos(session, tenant.filtro_empresa(empresa_id)), p
    )


@router.get(
    "/pagos-proveedor/{movimiento_id}", response_model=schemas.MovimientoDineroOut
)
def obtener_pago(
    movimiento_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `accounting.pago_requiere_aprobacion`: el aviso decía que
    un pago espera aprobación y no había forma de ir a mirar cuál."""
    return exigir_pago(session, movimiento_id, tenant)


@router.post(
    "/pagos-proveedor/{movimiento_id}/ejecutar", response_model=schemas.MovimientoDineroOut
)
def ejecutar_pago(
    movimiento_id: uuid.UUID,
    body: schemas.EjecutarPagoIn,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pago(session, movimiento_id, tenant)
    puede_aprobar = tiene_permiso(session, actor.id, PAGO_APROBAR)
    movimiento = pagos.ejecutar_pago(
        session,
        movimiento_id,
        actor_id=actor.id,
        puede_aprobar_monto=puede_aprobar,
        umbral=settings.accounting_umbral_aprobacion_pago,
        medio_pago=body.medio_pago,
        constancia=body.constancia,
    )
    session.commit()
    return movimiento


@router.post(
    "/pagos-proveedor/{movimiento_id}/rechazar", response_model=schemas.MovimientoDineroOut
)
def rechazar_pago(
    movimiento_id: uuid.UUID,
    actor: Usuario = Depends(require_permission(PAGO_GESTIONAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pago(session, movimiento_id, tenant)
    movimiento = pagos.rechazar_pago(session, movimiento_id, actor_id=actor.id)
    session.commit()
    return movimiento


# --- Caja (PROC-CTB-001/002) — slice mínimo, ver módulo application/caja.py -----
@router.post("/cajas/apertura", response_model=schemas.AperturaCajaOut, status_code=201)
def abrir_caja(
    body: schemas.AbrirCajaIn,
    actor: Usuario = Depends(require_permission(CAJA_OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Abre el turno: el cajero cuenta el fondo y verifica los POS de tarjeta
    (RN-POS-003/010).

    **La abre él solo** (RN-MDP-008): alcanza con `accounting.caja_operar`,
    el permiso que su rol ya tiene. Sin elevación de PIN — exigirla obligaba
    a que un encargado viniera a firmar cada apertura, y en el local eso se
    terminaba resolviendo dejando la sesión del encargado abierta en la caja.

    Un faltante de sencillo o un POS averiado **no impiden abrir**
    (RN-POS-011): quedan reportados y el local abre en su horario.
    """
    exigir_punto_venta(session, body.punto_venta_id, tenant)
    apertura = caja.abrir_caja(
        session,
        punto_venta_id=body.punto_venta_id,
        cajero_id=actor.id,
        monto_declarado=body.monto_declarado,
        detalle_denominaciones=body.detalle_denominaciones,
        pos_verificados=[p.model_dump() for p in body.pos_verificados or []],
    )
    session.commit()
    return apertura


@router.post(
    "/cajas/apertura/{apertura_caja_id}/cierre", response_model=schemas.CierreCajaOut
)
def cerrar_caja(
    apertura_caja_id: uuid.UUID,
    body: schemas.CerrarCajaIn,
    actor: Usuario = Depends(require_permission(CAJA_OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Cierra el turno contra el conteo por denominación (RN-POS-007).

    **Lo cierra el cajero solo** (RN-MDP-008), sin elevación de PIN. El
    efectivo queda `en_caja` a su nombre; entregárselo al encargado es un
    acto aparte y posterior, y ese sí lo firma quien recibe
    (`POST /cajas/custodias/{id}/entregar`, RN-MDP-002).

    Si el cierre venía reabierto, este mismo endpoint lo recalcula sobre el
    registro existente — un turno tiene un solo cierre, con su historial de
    correcciones.
    """
    exigir_apertura_caja(session, apertura_caja_id, tenant)
    cierre = caja.cerrar_caja(
        session,
        apertura_caja_id,
        cajero_id=actor.id,
        detalle_denominaciones=body.detalle_denominaciones,
        custodia=body.custodia,
        descuadre_atribucion=body.descuadre_atribucion,
        reportes_pos=[r.model_dump(mode="json") for r in body.reportes_pos or []] or None,
    )
    session.commit()
    return cierre


@router.post(
    "/cajas/cierres/{cierre_id}/reabrir", response_model=schemas.CierreCajaOut
)
def reabrir_cierre(
    cierre_id: uuid.UUID,
    body: schemas.ReabrirCierreIn,
    _: Usuario = Depends(require_permission(CAJA_OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Devuelve un cierre a `en_proceso` para recontar (RN-MDP-005).

    Solo mientras el efectivo siga en el local: una vez que llegó a
    contabilidad, corregir es un asiento, no un recuento.
    """
    exigir_cierre_caja(session, cierre_id, tenant)
    cierre = caja.reabrir_cierre(
        session,
        cierre_id,
        motivo=body.motivo,
        autorizado_por=_autorizado(body.autorizacion, CAJA_REABRIR),
    )
    session.commit()
    return cierre


@router.get(
    "/cajas/apertura/{apertura_caja_id}/custodia",
    response_model=schemas.CustodiaEfectivoOut,
)
def ver_custodia(
    apertura_caja_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_apertura_caja(session, apertura_caja_id, tenant)
    custodia = CustodiaEfectivoRepo(session).de_apertura(apertura_caja_id)
    if custodia is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "la caja todavía no fue cerrada"
        )
    return custodia


@router.post(
    "/cajas/custodias/{custodia_id}/entregar",
    response_model=schemas.CustodiaEfectivoOut,
)
def entregar_custodia(
    custodia_id: uuid.UUID,
    body: schemas.EntregarCustodiaIn,
    _: Usuario = Depends(require_permission(CAJA_OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Avanza la cadena de custodia; quien **recibe** firma con su PIN
    (RN-MDP-002).

    Desde ADR-049 este es el **único** endpoint del ciclo de caja que exige
    la elevación con `accounting.caja_relevar`, y el primer tramo
    (`en_caja → en_supervisor`) es la entrega que antes se daba por hecha al
    cerrar: el efectivo sale del cajón cuando alguien firma que lo recibió,
    no cuando el cajero terminó de contarlo.

    La sesión que opera la pantalla necesita `accounting.caja_operar`; quien
    firma es otro y aporta solo su PIN. Un cajero puede tener la pantalla
    abierta y **no** puede firmar la recepción: no tiene `caja_relevar`.
    """
    exigir_custodia(session, custodia_id, tenant)
    custodia = caja.entregar_custodia(
        session,
        custodia_id,
        estado_siguiente=body.estado_siguiente,
        receptor_id=_autorizado(body.autorizacion, CAJA_RELEVAR),
    )
    session.commit()
    return custodia


@router.post(
    "/cajas/apertura/{apertura_caja_id}/movimientos",
    response_model=schemas.MovimientoCajaOut,
    status_code=201,
)
def registrar_movimiento_caja(
    apertura_caja_id: uuid.UUID,
    body: schemas.MovimientoCajaIn,
    actor: Usuario = Depends(require_permission(CAJA_OPERAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Ingreso o retiro de efectivo del cajón durante el turno (RN-MDP-007).

    **Retirar exige autorización de supervisor** con su PIN (el token de
    `POST /auth/autorizar`); ingresar no, porque meter plata al cajón no es
    la operación de la que hay que desconfiar.
    """
    exigir_apertura_caja(session, apertura_caja_id, tenant)
    autorizado_por = None
    if body.tipo == "retiro":
        if not body.autorizacion:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "retirar efectivo requiere autorización de supervisor",
            )
        try:
            autorizado_por = autorizacion.verificar(body.autorizacion, CAJA_RETIRAR)
        except TokenInvalido as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    movimiento = caja.registrar_movimiento_caja(
        session,
        apertura_caja_id,
        tipo=body.tipo,
        monto=body.monto,
        motivo=body.motivo,
        registrado_por=actor.id,
        idempotency_key=body.idempotency_key,
        autorizado_por=autorizado_por,
    )
    session.commit()
    return movimiento


@router.get(
    "/cajas/apertura/{apertura_caja_id}/movimientos",
    response_model=list[schemas.MovimientoCajaOut],
)
def listar_movimientos_caja(
    apertura_caja_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_apertura_caja(session, apertura_caja_id, tenant)
    return MovimientoCajaRepo(session).de_apertura(apertura_caja_id)


@router.get("/cajas/turnos", response_model=list[schemas.TurnoCerradoOut])
def listar_turnos_cerrados(
    desde: date | None = None,
    hasta: date | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Turnos cerrados del rango (por defecto hoy), con su descuadre y el
    tramo de la cadena de custodia en el que está el efectivo."""
    desde = desde or fechas.hoy()
    hasta = hasta or desde
    if hasta < desde:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "`hasta` no puede ser anterior a `desde`"
        )
    return caja.turnos_cerrados(
        session, tenant.filtro_empresa(empresa_id), desde=desde, hasta=hasta
    )


@router.get(
    "/cajas/cierres/{cierre_caja_id}", response_model=schemas.CierreCajaDetalleOut
)
def obtener_cierre_caja(
    cierre_caja_id: uuid.UUID,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Destino de `accounting.cierre_caja_irregular`."""
    exigir_cierre_caja(session, cierre_caja_id, tenant)
    return caja.turno_cerrado(session, cierre_caja_id)


@router.get("/cajas/abiertas", response_model=list[schemas.CajaAbiertaOut])
def listar_cajas_abiertas(
    empresa_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    usuario: Usuario = Depends(get_current_user),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Con `sucursal_id`, **quien opera una caja** puede preguntar si la de su
    local ya está abierta; sin él hace falta `accounting.leer`, porque son las
    de toda la empresa.

    Antes exigía `accounting.leer` siempre, y un cajero —que tiene
    `caja_operar` y no `leer`— recibía 403. El PDV lo trataba como "no hay
    caja abierta" y le pedía abrir una que ya estaba abierta, para después
    negarle la apertura por duplicada: un callejón sin salida que empezaba
    como un permiso mal elegido.
    """
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
        check_permission(session, usuario, LEER, CAJA_OPERAR)
        return caja.cajas_abiertas(session, sucursal_id=sucursal_id)
    check_permission(session, usuario, LEER)
    return caja.cajas_abiertas(session, tenant.filtro_empresa(empresa_id))


# --- Inventario de POS de tarjeta (RN-POS-009/010) ---------------------------
@router.post("/pos-tarjeta", response_model=schemas.PosTarjetaOut, status_code=201)
def registrar_pos(
    body: schemas.PosTarjetaIn,
    _: Usuario = Depends(require_permission(POS_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    campos = body.model_dump()
    campos["empresa_id"] = tenant.empresa(campos["empresa_id"])
    if campos["sucursal_id"] is not None:
        tenant.exigir_sucursal(campos["sucursal_id"])
    pos = pos_uc.registrar_pos(session, **campos)
    session.commit()
    return pos


@router.get("/pos-tarjeta", response_model=list[schemas.PosTarjetaOut])
def listar_pos(
    empresa_id: uuid.UUID | None = None,
    sucursal_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Terminales de la sucursal más los de emergencia del pool (RN-POS-009)."""
    if sucursal_id is not None:
        tenant.exigir_sucursal(sucursal_id)
    return pos_uc.listar_pos(session, tenant.empresa(empresa_id), sucursal_id)


@router.patch("/pos-tarjeta/{pos_id}", response_model=schemas.PosTarjetaOut)
def actualizar_pos(
    pos_id: uuid.UUID,
    body: schemas.PosTarjetaPatch,
    _: Usuario = Depends(require_permission(POS_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_pos_tarjeta(session, pos_id, tenant)
    if body.sucursal_id is not None:
        tenant.exigir_sucursal(body.sucursal_id)
    pos = pos_uc.actualizar_pos(session, pos_id, **body.model_dump(exclude_unset=True))
    session.commit()
    return pos


@router.post("/arqueos", response_model=schemas.ArqueoOut, status_code=201)
def registrar_arqueo(
    body: schemas.ArqueoIn,
    actor: Usuario = Depends(require_permission(ARQUEO_REGISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    exigir_punto_venta(session, body.punto_venta_id, tenant)
    arqueo = caja.registrar_arqueo(session, realizado_por=actor.id, **body.model_dump())
    session.commit()
    return arqueo


# --- Plan Contable General Empresarial ----------------------------------------
@router.post(
    "/cuentas-contables/pcge", response_model=schemas.ImportacionPcgeOut, status_code=201
)
def importar_pcge(
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(CUENTA_ADMINISTRAR)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    """Siembra el Plan Contable General Empresarial en la empresa.

    Idempotente: correrlo dos veces no duplica nada. Es lo que hace que nadie
    tenga que inventar el número de una cuenta que ya existe.
    """
    resumen = pcge_uc.importar_pcge(session, empresa_id=tenant.empresa(empresa_id))
    session.commit()
    return resumen


# --- Estados financieros ------------------------------------------------------
@router.get(
    "/reportes/balance-comprobacion", response_model=schemas.BalanceComprobacionOut
)
def balance_comprobacion(
    desde: date | None = None,
    hasta: date | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return estados_financieros.balance_comprobacion(
        session, empresa_id=tenant.empresa(empresa_id), desde=desde, hasta=hasta
    )


@router.get("/reportes/libro-mayor", response_model=schemas.LibroMayorOut)
def libro_mayor(
    cuenta_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    # La empresa sale de la cuenta, no del tenant: `exigir_cuenta` ya validó
    # que esa cuenta está dentro del alcance, y un superusuario sin empresa
    # asignada no tiene ninguna que ofrecer.
    cuenta = exigir_cuenta(session, cuenta_id, tenant)
    return estados_financieros.libro_mayor(
        session,
        empresa_id=cuenta.empresa_id,
        cuenta_id=cuenta_id,
        desde=desde,
        hasta=hasta,
    )


@router.get(
    "/reportes/estado-situacion-financiera",
    response_model=schemas.EstadoSituacionFinancieraOut,
)
def estado_situacion_financiera(
    hasta: date | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return estados_financieros.estado_situacion_financiera(
        session, empresa_id=tenant.empresa(empresa_id), hasta=hasta
    )


@router.get("/reportes/estado-resultados", response_model=schemas.EstadoResultadosOut)
def estado_resultados(
    desde: date | None = None,
    hasta: date | None = None,
    empresa_id: uuid.UUID | None = None,
    _: Usuario = Depends(require_permission(LEER)),
    tenant: Tenant = Depends(get_tenant),
    session: Session = Depends(get_db),
):
    return estados_financieros.estado_resultados(
        session, empresa_id=tenant.empresa(empresa_id), desde=desde, hasta=hasta
    )
