"""Contrato de sincronización de `inventory` hacia el hub (ADR-009).

El hub necesita stock porque el listener `sales.venta_confirmada` corre en
su propio proceso: si el catálogo estuviera replicado pero el stock no, la
primera venta offline fallaría al descontar insumos.

`stock` es el único recurso que el hub también escribe localmente (cada
venta lo mueve). La nube gana en el pull, y eso es correcto **porque el
ciclo empuja antes de jalar**: para cuando el hub lee el stock de la nube,
la nube ya procesó las ventas del corte y ambos valores convergen.
"""

from sqlalchemy import select

from src.core.sync.contratos import RecursoSync
from src.modules.inventory.infrastructure.models import (
    Articulo,
    Categoria,
    CategoriaUdm,
    Receta,
    RecetaItem,
    Sku,
    Stock,
    UnidadMedida,
)

# Almacén es organización transversal (data-model §1); vive en
# users/infrastructure por historia. Import de modelo (no dominio)
# permitido — mismo precedente que `application/listeners.py`.
from src.modules.users.infrastructure.models import Almacen


def _articulos_de_la_empresa(alcance):
    return select(Articulo.id).where(Articulo.empresa_id == alcance.empresa_id)


def _almacenes_de_la_sucursal(alcance):
    return select(Almacen.id).where(Almacen.sucursal_id == alcance.sucursal_id)


RECURSOS = (
    RecursoSync(
        nombre="categoria_udm",
        modelo=CategoriaUdm,
        campos=("id", "nombre", "unidad_base_id", "updated_at"),
        filtro=lambda q, a: q,
        motivo="Catálogo global de unidades; `unidad_medida` cuelga de acá.",
    ),
    RecursoSync(
        nombre="unidad_medida",
        modelo=UnidadMedida,
        campos=("id", "categoria_udm_id", "nombre", "ratio", "updated_at"),
        filtro=lambda q, a: q,
        motivo="`articulo` y `receta` la referencian.",
    ),
    RecursoSync(
        nombre="categoria",
        modelo=Categoria,
        campos=(
            "id",
            "empresa_id",
            "nombre",
            "asiento_contable_config",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Categoria.empresa_id == a.empresa_id),
        motivo="Agrupa artículos y rutea ítems a las pantallas de cocina.",
    ),
    RecursoSync(
        nombre="articulo",
        modelo=Articulo,
        campos=(
            "id",
            "empresa_id",
            "id_interno",
            "nombre",
            "categoria_id",
            "unidad_medida_id",
            "tipo",
            "costo_promedio",
            "archivado",
            "deleted_at",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Articulo.empresa_id == a.empresa_id),
        motivo="Insumos y empaques que consume cada venta.",
    ),
    RecursoSync(
        nombre="sku",
        modelo=Sku,
        campos=(
            "id",
            "articulo_id",
            "codigo",
            "codigo_barras",
            "prioridad",
            "activo",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Sku.articulo_id.in_(_articulos_de_la_empresa(a))),
        motivo="El movimiento de stock es por SKU, no por artículo.",
    ),
    RecursoSync(
        nombre="receta",
        modelo=Receta,
        campos=(
            "id",
            "nombre",
            "rendimiento_cantidad",
            "rendimiento_unidad_medida_id",
            "flexible",
            "criterio_ajuste",
            "articulo_id",
            "updated_at",
        ),
        # Sin filtro de tenant a propósito: `receta` no tiene columna de
        # empresa en el modelo de datos, y acotarla exigiría cruzar
        # `producto_comercial` (dominio de sales) desde inventory. Se
        # replica completa — son recetas del propio grupo, en hardware del
        # propio grupo. Si el grupo llega a operar empresas que no deban
        # verse entre sí, `receta` necesita su columna de tenant primero.
        filtro=lambda q, a: q,
        motivo="Sin la receta, la venta offline no sabe qué insumos descontar.",
    ),
    RecursoSync(
        nombre="receta_item",
        modelo=RecetaItem,
        campos=("id", "receta_id", "articulo_id", "cantidad", "merma_pct", "updated_at"),
        filtro=lambda q, a: q,
        motivo="El detalle de la receta: qué y cuánto se descuenta.",
    ),
    RecursoSync(
        nombre="stock",
        modelo=Stock,
        campos=(
            "id",
            "almacen_id",
            "sku_id",
            "cantidad",
            "stock_minimo",
            "stock_maximo",
            "updated_at",
        ),
        filtro=lambda q, a: q.where(Stock.almacen_id.in_(_almacenes_de_la_sucursal(a))),
        motivo="Cantidad disponible en el local; la venta la descuenta offline.",
    ),
)
