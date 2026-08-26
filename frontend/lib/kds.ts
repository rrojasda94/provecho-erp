/**
 * Cliente y tipos del KDS (pantallas de cocina). Espeja `kds_schemas.py`.
 *
 * El avance NO se guarda en la pantalla: vive en `venta_item.estado_preparacion`
 * (RN-CUP-003, fuente única). Por eso tachar un ítem en una pantalla se ve en
 * todas las demás de la sucursal — cada una lee el mismo estado.
 */

import { pedir } from "./cliente-api";
import { pasosHastaListo, type EstadoItem } from "./kds-avance";
import type { Semaforo } from "./kds-semaforo";

export { ETIQUETA_ESTADO, siguienteToque } from "./kds-avance";
export type { EstadoItem } from "./kds-avance";
export { minutosDesde, nivelDe, reloj } from "./kds-semaforo";
export type { Nivel, Semaforo } from "./kds-semaforo";

export type Pantalla = {
  id: string;
  sucursal_id: string;
  nombre: string;
  tipo: "preparacion" | "despacho";
  categoria_ids: string[] | null;
  /** Eslabón de la cadena de preparación: armado (0) → horno (1) → …
   * (ADR-044). Despacho no está en la cadena; su orden solo lo ubica en la
   * lista de estaciones. */
  orden: number;
  activo: boolean;
};

export type ItemCola = {
  venta_item_id: string;
  producto: string;
  cantidad: string;
  estado: EstadoItem;
  /** Insumos que este plato NO lleva, ya con nombre (RN-COM-028). Vacío =
   * va completo. Es lo que hasta ahora se escribía en la nota libre, y que
   * ahora además deja de descontarse del almacén. */
  sin: string[];
  /** Lo que el plato lleva ADEMÁS: el sabor de la pizza, el queso extra.
   * Vienen anidados y no como ítems propios porque en cocina son el mismo
   * plato (RN-CUP-014) — sueltos, la tarjeta mostraba "1 Pizza Personal" y
   * "1 Peperoni" como si fueran dos cosas. */
  extras: { producto: string; cantidad: string }[];
  etapa_kds: number;
  /** En qué estación está la línea AHORA; `null` = ya salió de cocina. Es
   * lo que despacho lee para saber si el pedido espera por el horno o por
   * la barra (RN-CUP-013). */
  estacion: string | null;
};

export type PedidoHistorial = PedidoCola & {
  /** Cuándo se cerró el pedido. Es lo que se lee para decidir si «este» era
   * el que salió. */
  entregado_en: string;
};

export type PedidoCola = {
  venta_id: string;
  numero_orden: number;
  referencia_atencion: string | null;
  /** Dirección del delivery. Despacho arma la bolsa mirando la pantalla, así
   * que la ve acá y no solo en la comanda impresa. `null` fuera de delivery. */
  direccion_entrega: string | null;
  modalidad: string;
  canal: string;
  /** `venta` | `consumo_personal` (RN-COM-025): la cocina prioriza distinto
   * un pedido de cliente que la comida del turno. */
  tipo: string;
  consumo_motivo: string | null;
  estado_pedido: EstadoItem;
  /** Cuándo se tomó el pedido, en ISO. El cronómetro lo corre el navegador
   * (ver `kds-semaforo.ts`). */
  creado_en: string;
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
  orden: number;
};

/** Sucursal a la que puede quedar asignada una pantalla. Solo nombre e id:
 * el KDS no necesita saber nada más de un local. */
export type SucursalKds = { id: string; nombre: string };

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

  editarPantalla: (
    pantallaId: string,
    // `sucursal_id` muda la estación de local. La API lo rechaza si tiene
    // cola o si allá ya hay una con ese nombre.
    cuerpo: Partial<PantallaEnvio> & { activo?: boolean; sucursal_id?: string },
  ) => pedir<Pantalla>(`/kds/pantallas/${pantallaId}`, { metodo: "PATCH", cuerpo }),

  /** Baja definitiva. `activo: false` apaga la estación y la deja volver;
   * esto la saca y libera su nombre. La API la rechaza si tiene cola. */
  eliminarPantalla: (pantallaId: string) =>
    pedir<void>(`/kds/pantallas/${pantallaId}`, { metodo: "DELETE" }),

  categorias: () => pedir<Categoria[]>("/inventory/categorias"),

  /** Umbrales y colores que fijó Gerencia, ya resueltos. */
  configuracion: (sucursalId: string) =>
    pedir<Semaforo>(`/kds/configuracion?sucursal_id=${sucursalId}`),

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

  /** Deshace UN paso del avance. Sin cuerpo a propósito: no se salta a un
   * estado, se deshace lo último que se hizo (RN-CUP-002). */
  retroceder: (ventaItemId: string) =>
    pedir<ItemCola>(`/kds/items/${ventaItemId}/retroceder`, { metodo: "POST" }),

  historial: (pantallaId: string) =>
    pedir<PedidoHistorial[]>(`/kds/pantallas/${pantallaId}/historial`),

  /** El toque sobre la tarjeta de al lado en despacho. Deshacer algo que no
   * se entregó es un no-op, no un error. */
  deshacerEntrega: (ventaId: string) =>
    pedir<{ venta_id: string; estado_pedido: string }>(
      `/sales/ventas/${ventaId}/deshacer-entrega`,
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
