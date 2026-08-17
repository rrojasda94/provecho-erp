"""Datos para que las suites de Playwright recorran el ERP sin sembrar cada una lo suyo.

Sobre el seeder base (`python -m src.seeders.seed`), que ya deja la
organización real y el usuario `admin`, esto agrega lo que las pantallas
necesitan para poder operarse:

- **Caja y venta simple**: un punto de venta por sucursal, un encargado
  distinto del cajero, un terminal de tarjeta, y `Pizza E2E` —producto plano,
  un solo insumo— con precio vigente y stock.
- **Carta armada** (2026-08-15): `Menú E2E`, un producto **con variantes**,
  **grupo de opciones obligatorio** y **extras**, que es el modelo de nodos
  que describe ADR-035/ADR-038 y dibuja el lienzo. `Pizza E2E` no alcanza
  para eso: es deliberadamente plana, y las pruebas del lienzo dependen de
  que siga teniendo un único insumo — por eso la carta armada es un producto
  aparte y no un cambio sobre ella.
- **Compras** (2026-08-15): un proveedor y una orden de compra en borrador,
  con stock real en el almacén central.

Todo esto vive **acá y no en cada prueba** (`docs/engineering/testing-strategy.md`):
un test que crea sus datos por la UI prueba tres flujos para verificar uno, y
además cada rama que necesitaba un proveedor terminaba sembrando el suyo.

- **Caja y venta simple**: un punto de venta por sucursal, un encargado
  distinto del cajero, un terminal de tarjeta, y `Pizza E2E` —producto plano,
  un solo insumo— con precio vigente y stock.
- **Carta armada** (2026-08-15): `Menú E2E`, un producto **con variantes**,
  **grupo de opciones obligatorio** y **extras**, que es el modelo de nodos
  que describe ADR-035/ADR-038 y dibuja el lienzo. `Pizza E2E` no alcanza
  para eso: es deliberadamente plana, y las pruebas del lienzo dependen de
  que siga teniendo un único insumo — por eso la carta armada es un producto
  aparte y no un cambio sobre ella.
- **Compras** (2026-08-15): un proveedor y una orden de compra en borrador,
  con stock real en el almacén central.

Todo esto vive **acá y no en cada prueba** (`docs/engineering/testing-strategy.md`):
un test que crea sus datos por la UI prueba tres flujos para verificar uno, y
además cada rama que necesitaba un proveedor terminaba sembrando el suyo.

**El encargado sigue siendo otro usuario** aunque la caja ya no le pida
firma para abrirse (RN-MDP-008, ADR-049): es quien **recibe** el efectivo
cuando el turno cerró (`en_caja → en_supervisor`, RN-MDP-002), y eso exige
`accounting.caja_relevar` — permiso que el cajero no tiene ni debe tener.
Con un solo usuario la cadena de custodia no se puede recorrer.

Idempotente y **prohibido fuera de e2e**: crea un usuario con PIN conocido.
Correr: `python -m src.seeders.e2e`
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.core.database import SessionLocal
from src.modules.accounting.infrastructure.models import PosTarjeta
from src.modules.inventory.infrastructure.models import (
    Articulo,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)
from src.modules.purchases.application import ordenes as ordenes_uc
from src.modules.purchases.infrastructure.models import Proveedor
from src.modules.sales.application import catalogo as catalogo_uc
from src.modules.sales.application import clientes as clientes_uc
from src.modules.sales.application import precios as precios_uc
from src.modules.sales.infrastructure.models import (
    Cliente,
    ListaPrecio,
    MedioPago,
    Precio,
    ProductoComercial,
    PuntoVenta,
)
from src.modules.sales.infrastructure.repositories import ProductoComercialRepo
from src.modules.users.infrastructure.models import (
    Almacen,
    Empresa,
    Marca,
    Rol,
    Sucursal,
    Usuario,
    UsuarioRol,
    UsuarioSucursal,
)
from src.modules.users.infrastructure.security import hash_pin

ENCARGADO_USUARIO = "encargado_e2e"
ENCARGADO_PIN = "654321"
# El cajero existe para probar lo contrario que el encargado: qué **no** se
# ve. Es el rol con menos permisos que igual opera una pantalla, así que es
# con él que se verifica el gate del home y el de cada `layout.tsx`.
CAJERO_USUARIO = "cajero_e2e"
CAJERO_PIN = "111111"
PRODUCTO_NOMBRE = "Pizza E2E"
PRODUCTO_PRECIO = Decimal("25.00")

# --- Carta armada (variantes + grupo obligatorio + extras) -------------------
# `articulo.id_interno` y `producto_comercial.id_interno` son `String(4)`:
# todos los códigos de acá entran en cuatro caracteres a propósito. SQLite no
# valida el largo y Postgres sí, así que un código más largo pasaría las
# pruebas y reventaría recién al sembrar de verdad.
MENU_NOMBRE = "Menú E2E"
#: variante → (código, factor sobre la receta base, precio de lista)
MENU_VARIANTES: dict[str, tuple[str, Decimal, str]] = {
    "Simple": ("EM01", Decimal(1), "20.00"),
    "Doble": ("EM02", Decimal(2), "35.00"),
}
MENU_GRUPO = "Guarnición"
#: opción del grupo obligatorio → (insumo, gramos en la variante Simple)
MENU_GUARNICIONES: dict[str, tuple[str, int]] = {
    "Papas E2E": ("Papa E2E", 150),
    "Ensalada E2E": ("Lechuga E2E", 80),
}
#: extra suelto (fuera de grupo) → (insumo, gramos, precio)
MENU_EXTRAS: dict[str, tuple[str, int, str]] = {
    "Extra Queso E2E": ("Queso E2E", 60, "4.00"),
}
#: insumo → (código, costo unitario, stock inicial en el almacén central)
INSUMOS_MENU: dict[str, tuple[str, str, str]] = {
    "Papa E2E": ("EI01", "0.004", "5000"),
    "Lechuga E2E": ("EI02", "0.011", "3000"),
    "Queso E2E": ("EI03", "0.028", "4000"),
}

# --- Compras ----------------------------------------------------------------
PROVEEDOR_RAZON = "Distribuidora E2E SAC"
# `proveedor.ruc` es `String(11)`: once dígitos exactos, ni uno más.
PROVEEDOR_RUC = "20512345678"
# `orden_compra.idempotency_key` es UNIQUE y `crear_orden_compra` devuelve la
# orden existente si lo reconoce: es la idempotencia del seeder, no una
# comprobación aparte.
OC_IDEMPOTENCY = "seed-e2e-oc-0001"

# Cuenta de sacrificio: la prueba del bloqueo por intentos fallidos (ADR-050)
# le agota los cinco intentos y la deja inutilizable quince minutos. Gastar
# para eso al cajero o al encargado dejaría sin sesión a las pruebas que
# corran después, en un orden que Playwright no promete.
BLOQUEO_USUARIO = "bloqueo_e2e"
BLOQUEO_PIN = "222222"

# --- Padrón de clientes -----------------------------------------------------
# Un cliente **jurídico**: es el que Ventas → Clientes deja corregir, y el
# diálogo donde vive el botón «Buscar por RUC» (ADR-041). Sin ninguno
# sembrado la pantalla se abre vacía y no hay nada que abrir.
# La razón social está tecleada **mal a propósito**: el recorrido consiste en
# traerla de SUNAT, y una que ya está bien no muestra nada.
CLIENTE_RUC = "20610077782"
CLIENTE_RAZON = "razon social tecleada a mano"


def _primero(session: Session, modelo):
    return session.scalars(select(modelo)).first()


def sembrar_e2e(session: Session) -> dict:
    if settings.es_produccion:
        raise RuntimeError("el seeder e2e crea un usuario con PIN conocido")

    empresa = _primero(session, Empresa)
    marca = _primero(session, Marca)
    sucursal = _primero(session, Sucursal)
    if empresa is None or sucursal is None:
        raise RuntimeError("correr antes `python -m src.seeders.seed`")

    # Un punto de venta y un POS **por sucursal**, no solo por la primera:
    # el PDV resuelve su sucursal desde el usuario y con una sola sembrada
    # cae en la que no tiene caja, muestra "la sucursal no tiene puntos de
    # venta" y la prueba falla por el dato en vez de por el código.
    puntos_venta = []
    for indice, suc in enumerate(session.scalars(select(Sucursal)).all(), start=1):
        pv = session.scalar(select(PuntoVenta).where(PuntoVenta.sucursal_id == suc.id))
        if pv is None:
            pv = PuntoVenta(
                sucursal_id=suc.id,
                canal="trabajador",
                serie_boleta=f"B{indice:03d}",
                serie_factura=f"F{indice:03d}",
                politica_pago="adelantado",
            )
            session.add(pv)
            session.flush()
        puntos_venta.append(pv)

        serie_pos = f"POS-E2E-{indice:02d}"
        if session.scalar(select(PosTarjeta).where(PosTarjeta.serie == serie_pos)) is None:
            session.add(
                PosTarjeta(
                    empresa_id=empresa.id,
                    sucursal_id=suc.id,
                    serie=serie_pos,
                    codigo_comercio=f"999999{indice}",
                    operador="Izipay",
                    estado="operativo",
                    es_emergencia=False,
                )
            )
    punto_venta = puntos_venta[0]

    # `supervisor` es quien recibe el efectivo del cajón al terminar el
    # turno (RN-MDP-002): tiene `accounting.caja_relevar`, el permiso que
    # exige firmar un tramo de la cadena de custodia.
    _usuario_con_rol(session, ENCARGADO_USUARIO, ENCARGADO_PIN, "supervisor", sucursal)
    _usuario_con_rol(session, CAJERO_USUARIO, CAJERO_PIN, "cajero", sucursal)
    _usuario_con_rol(session, BLOQUEO_USUARIO, BLOQUEO_PIN, "cajero", sucursal)

    producto = session.scalar(
        select(ProductoComercial).where(ProductoComercial.nombre == PRODUCTO_NOMBRE)
    )
    if producto is None:
        producto = _crear_producto_vendible(session, empresa, marca)

    if session.scalar(select(MedioPago)) is None:
        session.add(
            MedioPago(
                empresa_id=empresa.id,
                nombre="Efectivo",
                direccion="cobro",
                tipo="efectivo",
            )
        )

    menu = _sembrar_menu(session, empresa, marca)
    compras = _sembrar_compras(session, empresa)
    cliente = _sembrar_cliente(session, empresa)

    return {
        "sucursales": len(puntos_venta),
        "punto_venta_id": str(punto_venta.id),
        "producto": PRODUCTO_NOMBRE,
        **menu,
        **compras,
        **cliente,
    }


def _sembrar_cliente(session: Session, empresa: Empresa) -> dict:
    """Un cliente jurídico en el padrón del grupo (RN-PTS-001).

    Se crea por el caso de uso y no armando el modelo a mano: `crear_cliente`
    es quien decide que once dígitos son un RUC y por lo tanto un cliente
    jurídico, y un seeder que lo esquiva puede dejar en la base una fila que
    el ERP nunca produciría.
    """
    cliente = session.scalar(select(Cliente).where(Cliente.ruc == CLIENTE_RUC))
    if cliente is None:
        cliente = clientes_uc.crear_cliente(
            session,
            grupo_id=clientes_uc.grupo_de_empresa(session, empresa.id),
            nombre=CLIENTE_RAZON,
            numero_documento=CLIENTE_RUC,
        )
        session.flush()
    return {"cliente_ruc": CLIENTE_RUC}


def _usuario_con_rol(
    session: Session, username: str, pin: str, rol: str, sucursal: Sucursal
) -> Usuario:
    usuario = session.scalar(select(Usuario).where(Usuario.username == username))
    if usuario is not None:
        return usuario
    usuario = Usuario(
        username=username, pin_hash=hash_pin(pin), tipo="humano", activo=True
    )
    session.add(usuario)
    session.flush()
    session.add(
        UsuarioRol(
            usuario_id=usuario.id,
            rol_id=session.scalar(select(Rol).where(Rol.nombre == rol)).id,
        )
    )
    session.add(UsuarioSucursal(usuario_id=usuario.id, sucursal_id=sucursal.id))
    return usuario


def _crear_producto_vendible(session, empresa, marca) -> ProductoComercial:
    """Producto con receta y stock: sin stock del insumo la venta se rechaza,
    y la prueba fallaría por el dato en vez de por el código."""
    udm = _unidad_base(session)

    harina = Articulo(
        empresa_id=empresa.id,
        # `articulo.id_interno` es `String(4)`. Decía "E2E-H001" y entraba
        # igual porque SQLite no aplica el largo de un VARCHAR; contra
        # Postgres la siembra habría reventado, y en la pantalla el código no
        # se podía ni reenviar sin recibir un 422 de su propio valor.
        id_interno="EH01",
        nombre="Harina E2E",
        unidad_medida_id=udm.id,
        tipo="insumo",
        # Con costo 0 el lienzo de nodos simula un plato que cuesta S/ 0.00 y
        # la prueba de que una resta baja el costo no puede distinguir "bajó"
        # de "nunca hubo". Un costo cualquiera > 0 alcanza.
        costo_promedio=Decimal("2.50"),
    )
    session.add(harina)
    session.flush()
    sku = Sku(articulo_id=harina.id, codigo="SKU-E2E-HARINA")
    receta = Receta(
        empresa_id=empresa.id,
        nombre="Base E2E",
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=udm.id,
    )
    session.add_all([sku, receta])
    session.flush()
    session.add(
        RecetaItem(receta_id=receta.id, articulo_id=harina.id, cantidad=Decimal("0.25"))
    )

    _stock(session, sku, Decimal(1000))

    producto = ProductoComercial(
        # Mismo caso que `harina`: la columna es `String(4)`.
        id_interno="EP01",
        marca_id=marca.id,
        nombre=PRODUCTO_NOMBRE,
        receta_id=receta.id,
    )
    session.add(producto)
    session.flush()

    session.add(
        Precio(
            lista_precio_id=_lista_precio(session, marca).id,
            producto_comercial_id=producto.id,
            monto=PRODUCTO_PRECIO,
        )
    )
    return producto


# --- Piezas compartidas ------------------------------------------------------


def _unidad_base(session: Session) -> UnidadMedida:
    """La unidad con la que se miden los insumos sembrados acá."""
    categoria = _primero(session, CategoriaUdm)
    if categoria is None:
        categoria = CategoriaUdm(nombre="Peso")
        session.add(categoria)
        session.flush()
    udm = session.scalar(
        select(UnidadMedida).where(UnidadMedida.categoria_udm_id == categoria.id)
    )
    if udm is None:
        udm = UnidadMedida(categoria_udm_id=categoria.id, nombre="Kilo")
        session.add(udm)
        session.flush()
    return udm


def _lista_precio(session: Session, marca: Marca) -> ListaPrecio:
    lista = session.scalar(select(ListaPrecio).where(ListaPrecio.marca_id == marca.id))
    if lista is None:
        lista = ListaPrecio(
            marca_id=marca.id, nombre="Regular", vigente_desde=date(2020, 1, 1)
        )
        session.add(lista)
        session.flush()
    return lista


def _stock(session: Session, sku: Sku, cantidad: Decimal) -> Stock:
    """Deja el stock del SKU **en** `cantidad`, no le suma.

    Fijar el valor absoluto es lo que hace idempotente a esta parte: los
    seeders se vuelven a correr, y uno que sumara dejaría una base distinta
    en cada corrida. `stock` tiene UNIQUE (almacen_id, sku_id).
    """
    almacen = session.scalar(select(Almacen))
    fila = session.scalar(
        select(Stock).where(Stock.almacen_id == almacen.id, Stock.sku_id == sku.id)
    )
    if fila is None:
        fila = Stock(almacen_id=almacen.id, sku_id=sku.id)
        session.add(fila)
    fila.cantidad = cantidad
    session.flush()
    return fila


def _insumo(
    session: Session,
    empresa: Empresa,
    udm: UnidadMedida,
    nombre: str,
    id_interno: str,
    costo: str,
    stock: str,
) -> Articulo:
    """Artículo + SKU + stock, en una sola pieza idempotente.

    Sin SKU el consumo de la venta no descuenta nada y queda una incidencia:
    la pantalla se ve bien y el inventario no se mueve. Sin stock, la venta
    se rechaza y la prueba falla por el dato en vez de por el código.
    """
    art = session.scalar(
        select(Articulo).where(
            Articulo.nombre == nombre, Articulo.empresa_id == empresa.id
        )
    )
    if art is None:
        art = Articulo(
            empresa_id=empresa.id,
            id_interno=id_interno,
            nombre=nombre,
            unidad_medida_id=udm.id,
            tipo="insumo",
            costo_promedio=Decimal(costo),
        )
        session.add(art)
        session.flush()
    sku = session.scalar(select(Sku).where(Sku.articulo_id == art.id))
    if sku is None:
        sku = Sku(articulo_id=art.id, codigo=f"SKU-{id_interno}-E2E")
        session.add(sku)
        session.flush()
    _stock(session, sku, Decimal(stock))
    return art


def _receta(
    session: Session,
    empresa: Empresa,
    udm: UnidadMedida,
    nombre: str,
    lineas: list[tuple[Articulo, Decimal]],
) -> Receta:
    receta = session.scalar(
        select(Receta).where(Receta.nombre == nombre, Receta.empresa_id == empresa.id)
    )
    if receta is not None:
        return receta
    receta = Receta(
        empresa_id=empresa.id,
        nombre=nombre,
        rendimiento_cantidad=Decimal(1),
        rendimiento_unidad_medida_id=udm.id,
    )
    session.add(receta)
    session.flush()
    for articulo, cantidad in lineas:
        session.add(
            RecetaItem(receta_id=receta.id, articulo_id=articulo.id, cantidad=cantidad)
        )
    session.flush()
    return receta


def _producto(session: Session, id_interno: str, **campos) -> ProductoComercial:
    """`crear_producto` levanta `Conflicto` si el código ya existe: se mira antes.

    Se pasa por el caso de uso y no por el ORM a propósito — es el que sabe
    de la herencia del padre (ADR-042), del nombre en formato título y de que
    una variante no puede ser extra.
    """
    existente = session.scalar(
        select(ProductoComercial).where(ProductoComercial.id_interno == id_interno)
    )
    if existente is not None:
        return existente
    return catalogo_uc.crear_producto(session, id_interno=id_interno, **campos)


def _precio(session: Session, lista: ListaPrecio, producto, monto: str) -> None:
    """Fija el precio si el producto no tiene uno en esta lista.

    Una lista de precios no se edita —corregir es lista nueva—, así que
    `fijar_precio` sobre un producto ya tarifado levanta `Conflicto`. Se
    consulta antes en vez de atrapar la excepción: un `rollback` acá se
    llevaría puesto todo lo sembrado y todavía sin commitear.
    """
    ya = session.scalar(
        select(Precio).where(
            Precio.lista_precio_id == lista.id,
            Precio.producto_comercial_id == producto.id,
        )
    )
    if ya is not None:
        return
    precios_uc.fijar_precio(
        session,
        lista_precio_id=lista.id,
        producto_comercial_id=producto.id,
        monto=Decimal(monto),
    )


# --- Carta armada ------------------------------------------------------------


def _sembrar_menu(session: Session, empresa: Empresa, marca: Marca) -> dict:
    """`Menú E2E`: padre → variantes → grupo obligatorio → extras.

    Es el modelo de nodos completo (RN-PRD-004, ADR-035/038) que `Pizza E2E`
    no puede representar sin dejar de ser plana. El padre agrupa y no se
    vende: sin receta y sin precio (RN-COM-022).
    """
    udm = _unidad_base(session)
    lista = _lista_precio(session, marca)
    insumos = {
        nombre: _insumo(session, empresa, udm, nombre, codigo, costo, stock)
        for nombre, (codigo, costo, stock) in INSUMOS_MENU.items()
    }
    base = insumos["Queso E2E"]

    padre = _producto(session, "EM00", marca_id=marca.id, nombre=MENU_NOMBRE)

    for indice, (tamano, (codigo, factor, precio)) in enumerate(MENU_VARIANTES.items()):
        receta = _receta(
            session,
            empresa,
            udm,
            f"Base {MENU_NOMBRE} {tamano}",
            [(base, Decimal("0.05") * factor)],
        )
        variante = _producto(
            session,
            codigo,
            marca_id=marca.id,
            nombre=f"{MENU_NOMBRE} {tamano}",
            receta_id=receta.id,
            producto_padre_id=padre.id,
            orden=indice,
        )
        _precio(session, lista, variante, precio)
        # Un dict y no siete parámetros repetidos, igual que `pizzas_demo`:
        # `indice` viaja porque los códigos de las opciones se numeran por
        # variante — cada par (variante, opción) es un producto distinto, ya
        # que su receta cambia con el tamaño.
        ctx = {
            "empresa": empresa,
            "udm": udm,
            "lista": lista,
            "insumos": insumos,
            "variante": variante,
            "indice": indice,
            "factor": factor,
        }
        _grupo_obligatorio(session, ctx)
        _extras_sueltos(session, ctx)

    return {
        "menu": MENU_NOMBRE,
        "menu_id": str(padre.id),
        "variantes": len(MENU_VARIANTES),
        "guarniciones": len(MENU_GUARNICIONES),
        "extras": len(MENU_EXTRAS),
    }


def _opcion(session: Session, ctx: dict, codigo: str, nombre: str, insumo, gramos: int):
    """Un extra con su receta, escalada al tamaño de la variante."""
    variante = ctx["variante"]
    receta = _receta(
        session,
        ctx["empresa"],
        ctx["udm"],
        f"{nombre} {variante.nombre}",
        [(ctx["insumos"][insumo], Decimal(gramos) * ctx["factor"] / 1000)],
    )
    return _producto(
        session,
        codigo,
        marca_id=variante.marca_id,
        nombre=nombre,
        receta_id=receta.id,
        es_extra=True,
    )


def _grupo_obligatorio(session: Session, ctx: dict) -> None:
    """El grupo `minimo=1, maximo=1`: elegir uno no es opcional (RN-COM-023)."""
    variante, lista = ctx["variante"], ctx["lista"]
    grupo = next(
        (
            g
            for g in ProductoComercialRepo(session).grupos_de(variante.id)
            if g.nombre == MENU_GRUPO
        ),
        None,
    )
    if grupo is None:
        grupo = catalogo_uc.crear_grupo_opcion(
            session, producto_id=variante.id, nombre=MENU_GRUPO, minimo=1, maximo=1
        )

    for i, (nombre, (insumo, gramos)) in enumerate(MENU_GUARNICIONES.items()):
        # Prefijo `E` como todo lo de este seeder: `pizzas_demo` numera sus
        # opciones `S00`/`X00`, y con el mismo esquema una base que tenga los
        # dos seeders haría que `_producto` devolviera el extra de la pizza y
        # lo colgara del menú, en silencio.
        opcion = _opcion(session, ctx, f"EG{ctx['indice']}{i}", nombre, insumo, gramos)
        _vincular(session, variante.id, opcion.id, grupo.id, maximo=1)
        # La guarnición no cobra aparte —la variante ya lleva el precio
        # completo—, pero **necesita precio de lista igual**: la carta
        # descarta todo extra sin precio vigente y el grupo saldría vacío,
        # que con `minimo=1` deja el producto imposible de vender.
        _precio(session, lista, opcion, "0")


def _extras_sueltos(session: Session, ctx: dict) -> None:
    """Extras fuera de grupo: opcionales y con precio propio (RN-COM-021)."""
    variante = ctx["variante"]
    for i, (nombre, (insumo, gramos, monto)) in enumerate(MENU_EXTRAS.items()):
        extra = _opcion(session, ctx, f"EX{ctx['indice']}{i}", nombre, insumo, gramos)
        _vincular(session, variante.id, extra.id, None, maximo=2)
        _precio(session, ctx["lista"], extra, monto)


def _vincular(session: Session, producto_id, extra_id, grupo_id, maximo: int) -> None:
    repo = ProductoComercialRepo(session)
    if repo.admite_extra(producto_id, extra_id) is not None:
        return
    catalogo_uc.vincular_extra(
        session,
        producto_id=producto_id,
        extra_id=extra_id,
        maximo=maximo,
        grupo_id=grupo_id,
    )


# --- Compras -----------------------------------------------------------------


def _sembrar_compras(session: Session, empresa: Empresa) -> dict:
    """Un proveedor y una orden de compra en borrador.

    **En borrador y no emitida** a propósito: emitirla es el paso que una
    prueba de uso quiere dar por la pantalla —incluye el umbral de
    aprobación—, y una orden que llega ya emitida se lo saltea. La recepción
    sí necesitaría una emitida; cuando alguna rama la necesite, que la emita
    la prueba pasando por el candado, que es la regla de la casa.

    `Proveedor` se instancia directo en vez de por `crear_proveedor`: ese caso
    de uso consulta el RUC contra **Factiliza**, y un seeder que hace una
    llamada externa falla sin red y siembra distinto según qué responda.
    """
    proveedor = session.scalar(
        select(Proveedor).where(
            Proveedor.empresa_id == empresa.id, Proveedor.ruc == PROVEEDOR_RUC
        )
    )
    if proveedor is None:
        proveedor = Proveedor(
            empresa_id=empresa.id,
            tipo="juridico",
            razon_social=PROVEEDOR_RAZON,
            ruc=PROVEEDOR_RUC,
            contacto="compras@e2e.test",
            condicion_pago="credito",
            plazo_dias_credito=30,
            clasificacion="preferente",
        )
        session.add(proveedor)
        session.flush()

    almacen = session.scalar(select(Almacen))
    # `orden_compra.creado_por` es FK real a `usuario.id`, no un texto.
    autor = session.scalar(select(Usuario).where(Usuario.username == "admin"))
    if autor is None:
        raise RuntimeError("correr antes `python -m src.seeders.seed`")

    articulos = session.scalars(
        select(Articulo)
        .where(Articulo.empresa_id == empresa.id, Articulo.tipo == "insumo")
        .order_by(Articulo.id_interno)
        .limit(2)
    ).all()

    orden = ordenes_uc.crear_orden_compra(
        session,
        proveedor_id=proveedor.id,
        almacen_destino_id=almacen.id,
        creado_por=autor.id,
        idempotency_key=OC_IDEMPOTENCY,
        items=[
            {
                "articulo_id": art.id,
                "cantidad": Decimal(10),
                "costo_unitario": (art.costo_promedio or Decimal("1.00")),
            }
            for art in articulos
        ],
    )

    return {
        "proveedor": PROVEEDOR_RAZON,
        "proveedor_id": str(proveedor.id),
        "orden_compra_id": str(orden.id),
        "orden_compra_estado": orden.estado,
    }


def main() -> None:
    with SessionLocal() as session:
        datos = sembrar_e2e(session)
        session.commit()
    print(f"Seed e2e listo: {datos}")


if __name__ == "__main__":
    main()
