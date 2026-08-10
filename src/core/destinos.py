"""A dónde lleva un reporte: `referencia_tipo` → endpoint del módulo dueño.

**El problema que resuelve (ADR-036).** Un reporte emitido guarda
`referencia_tipo` + `referencia_id` desde ADR-033, pero nadie sabía qué hacer
con ese par: el reporte decía «ajuste de inventario fuera de margen» y quien
lo leía tenía que adivinar en qué pantalla se aprueba o se rechaza. Un dato
al que no se puede llegar es una línea de texto.

**Por qué vive en `core` y no en el módulo.** Lo leen dos consumidores que no
pueden verse entre sí: `modules/reports/api` (para el reporte emitido) y
`core/reportes` (para las filas del tablero, ADR-024). Ponerlo en
`reports/domain` lo dejaría fuera del alcance de `core/reportes`
(`test_core_no_importa_el_dominio_de_ningun_modulo`), y ponerlo en `shared` lo
dejaría fuera del alcance de `reports.domain`
(`test_domain_no_conoce_ni_core_ni_otros_modulos`). `core` es la única capa
que los dos pueden leer.

**Rutas de API, no de UI.** Acá va el endpoint; la ruta de pantalla la traduce
el frontend (`frontend/lib/destinos.ts`). El backend no conoce el router de
Next.js, y duplicar el permiso en el cliente sería una segunda matriz de RBAC
que se desincroniza.

El `permiso` es el del **módulo dueño**, igual que en el catálogo de emisiones:
ser destinatario de un reporte no da acceso al dato (RN-REP-002), así que el
cliente esconde el botón que llevaría a un 403.

`tests/test_destinos.py` congela dos cosas: que todo `referencia_tipo` del
catálogo tenga entrada acá, y que toda `ruta` corresponda a un endpoint
realmente montado. Un rename de endpoint rompe el enlace en CI y no en
producción.
"""

import uuid
from dataclasses import dataclass

# Prefijo que la app monta delante de todos los routers de negocio. Vive acá
# porque la ruta almacenada es la del router (sin prefijo) y el enlace que se
# entrega al cliente sí lo lleva.
PREFIJO_API = "/api/v1"


@dataclass(frozen=True)
class Destino:
    """Dónde se mira —y se resuelve— el hecho que el reporte informa."""

    # Ruta del endpoint sin `PREFIJO_API`, con `{id}` como único marcador.
    ruta: str
    # Permiso del módulo dueño. El cliente oculta lo que no alcanza.
    permiso: str
    # Qué se va a hacer ahí. Es el rótulo del botón: «Ver la venta» dice más
    # que «Ir al destino», y quien lee el reporte decide si vale la pena.
    etiqueta: str


DESTINOS: dict[str, Destino] = {
    "venta": Destino("/sales/ventas/{id}", "sales.leer", "Ver la venta"),
    "sku": Destino("/inventory/skus/{id}", "inventory.leer", "Ver el stock del SKU"),
    "articulo": Destino(
        "/inventory/articulos/{id}", "inventory.leer", "Ver el artículo"
    ),
    "lote": Destino("/inventory/lotes/{id}", "inventory.leer", "Ver el lote"),
    "categoria": Destino(
        "/inventory/categorias/{id}", "inventory.leer", "Ver la categoría"
    ),
    "devolucion": Destino(
        "/inventory/devoluciones/{id}", "inventory.leer", "Ver la devolución"
    ),
    "ajuste": Destino(
        "/inventory/ajustes/{id}", "inventory.leer", "Revisar el ajuste"
    ),
    "cierre_caja": Destino(
        "/accounting/cajas/cierres/{id}", "accounting.leer", "Ver el cierre de caja"
    ),
    "movimiento_dinero": Destino(
        "/accounting/pagos-proveedor/{id}", "accounting.leer", "Ver el pago"
    ),
    "orden_produccion": Destino(
        "/production/ordenes/{id}", "production.leer", "Ver la orden de producción"
    ),
    # La única entrada cuyo permiso es de `reports`, y con razón: la entidad
    # es de `reports`. No es una segunda matriz de permisos.
    "escalamiento": Destino(
        "/reports/escalamientos/{id}", "reports.leer", "Ver el escalamiento"
    ),
}


def obtener(tipo: str | None) -> Destino | None:
    return DESTINOS.get(tipo) if tipo else None


def url(tipo: str | None, referencia_id: uuid.UUID | str | None) -> str | None:
    """El enlace completo, o `None` si el hecho no apunta a ninguna parte.

    Un reporte sin referencia no es un error: `hueco` y `fuga` de la matriz
    hablan de la distribución, no de una entidad.
    """
    destino = obtener(tipo)
    if destino is None or referencia_id is None:
        return None
    return PREFIJO_API + destino.ruta.format(id=referencia_id)
