"""Datos mínimos para que las pruebas e2e puedan recorrer el flujo del dinero.

Sobre el seeder base (`python -m src.seeders.seed`), que ya deja la
organización real y el usuario `admin`, esto agrega lo que el PDV necesita
para abrir caja y vender: un punto de venta, un encargado distinto del
cajero, un terminal de tarjeta, un producto con precio vigente y stock del
insumo que su receta consume.

**El encargado tiene que ser otro usuario**: `abrir_caja` rechaza que el
cajero se releve a sí mismo (RN-MDP-002), así que un seed con un solo
usuario no puede abrir caja y la prueba fallaría por el dato, no por el
código.

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
from src.modules.sales.infrastructure.models import (
    ListaPrecio,
    MedioPago,
    Precio,
    ProductoComercial,
    PuntoVenta,
)
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

    # `supervisor` es quien releva la caja (RN-MDP-002): tiene
    # `accounting.caja_relevar`, que es el permiso que la apertura exige.
    _usuario_con_rol(session, ENCARGADO_USUARIO, ENCARGADO_PIN, "supervisor", sucursal)
    _usuario_con_rol(session, CAJERO_USUARIO, CAJERO_PIN, "cajero", sucursal)

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

    return {
        "sucursales": len(puntos_venta),
        "punto_venta_id": str(punto_venta.id),
        "producto": PRODUCTO_NOMBRE,
    }


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

    almacen = session.scalar(select(Almacen))
    session.add(Stock(almacen_id=almacen.id, sku_id=sku.id, cantidad=Decimal(1000)))

    producto = ProductoComercial(
        # Mismo caso que `harina`: la columna es `String(4)`.
        id_interno="EP01",
        marca_id=marca.id,
        nombre=PRODUCTO_NOMBRE,
        receta_id=receta.id,
    )
    session.add(producto)
    session.flush()

    lista = session.scalar(select(ListaPrecio).where(ListaPrecio.marca_id == marca.id))
    if lista is None:
        lista = ListaPrecio(
            marca_id=marca.id, nombre="Regular", vigente_desde=date(2020, 1, 1)
        )
        session.add(lista)
        session.flush()
    session.add(
        Precio(
            lista_precio_id=lista.id,
            producto_comercial_id=producto.id,
            monto=PRODUCTO_PRECIO,
        )
    )
    return producto


def main() -> None:
    with SessionLocal() as session:
        datos = sembrar_e2e(session)
        session.commit()
    print(f"Seed e2e listo: {datos}")


if __name__ == "__main__":
    main()
