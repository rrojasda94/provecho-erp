/**
 * Cliente y tipos del KDS (pantallas de cocina). Espeja `kds_schemas.py`.
 *
 * El avance NO se guarda en la pantalla: vive en `venta_item.estado_preparacion`
 * (RN-CUP-003, fuente única). Por eso tachar un ítem en una pantalla se ve en
 * todas las demás de la sucursal — cada una lee el mismo estado.
 */

import { pedir } from "./cliente-api";
import { pasosHastaListo, type EstadoItem } from "./kds-avance";

export { ETIQUETA_ESTADO } from "./kds-avance";
export type { EstadoItem } from "./kds-avance";

export type Pantalla = {
  id: string;
  sucursal_id: string;
  nombre: string;
  tipo: "preparacion" | "despacho";
  categoria_ids: string[] | null;
  activo: boolean;
};

export type ItemCola = {
  venta_item_id: string;
  producto: string;
  cantidad: string;
  estado: EstadoItem;
  /** Insumos que este plato NO lleva, ya con nombre (RN-COM-025). Vacío =
   * va completo. Es lo que hasta ahora se escribía en la nota libre, y que
   * ahora además deja de descontarse del almacén. */
  sin: string[];
};

export type PedidoCola = {
  venta_id: string;
  numero_orden: number;
  referencia_atencion: string | null;
  modalidad: string;
  canal: string;
  estado_pedido: EstadoItem;
  items: ItemCola[];
};

/** Categoría de producto comercial — el filtro que rutea cada ítem a su
 * estación (pizzas → horno, bebidas → barra). Vive en `inventory`, que es
 * dueño del catálogo; `sales` la reusa. */
export type Categoria = { id: string; nombre: string };

export type PantallaEnvio = {
  nombre: string;
  tipo: "preparacion" | "despacho";
  categoria_ids: string[] | null;
};

export const apiKds = {
  cola: (pantallaId: string) =>
    pedir<PedidoCola[]>(`/kds/pantallas/${pantallaId}/cola`),

  pantallas: (sucursalId: string) =>
    pedir<Pantalla[]>(`/kds/pantallas?sucursal_id=${sucursalId}`),

  crearPantalla: (sucursalId: string, cuerpo: PantallaEnvio) =>
    pedir<Pantalla>("/kds/pantallas", {
      metodo: "POST",
      cuerpo: { sucursal_id: sucursalId, ...cuerpo },
    }),

  editarPantalla: (pantallaId: string, cuerpo: Partial<PantallaEnvio> & { activo?: boolean }) =>
    pedir<Pantalla>(`/kds/pantallas/${pantallaId}`, { metodo: "PATCH", cuerpo }),

  categorias: () => pedir<Categoria[]>("/inventory/categorias"),

  avanzar: (ventaItemId: string, estado: EstadoItem) =>
    pedir<ItemCola>(`/kds/items/${ventaItemId}/avanzar`, {
      metodo: "POST",
      cuerpo: { estado },
    }),

  entregar: (ventaId: string) =>
    pedir<{ venta_id: string; estado: string }>(
      `/sales/ventas/${ventaId}/entrega`,
      { metodo: "POST" },
    ),
};

/**
 * Tachar un ítem = marcarlo preparado en UN toque (patrón Odoo: se hace
 * cocinando, con las manos ocupadas). La API solo acepta avanzar de a un
 * estado, así que desde `pendiente` se encadenan los dos pasos —
 * `en_preparacion` queda registrado igual, que es lo que ven las otras
 * pantallas mientras tanto.
 */
export async function marcarPreparado(item: ItemCola): Promise<void> {
  for (const estado of pasosHastaListo(item.estado)) {
    await apiKds.avanzar(item.venta_item_id, estado);
  }
}
