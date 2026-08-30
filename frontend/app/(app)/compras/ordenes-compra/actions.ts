"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { cuerpoDeFactura, faltaEnLaFactura } from "@/lib/factura-proveedor";

export type EstadoOrdenCompra = { error: string; ok: boolean };

type ItemForm = { articuloId: string; cantidad: string; costoUnitario: string };

function leerItems(formData: FormData): ItemForm[] {
  const articulos = formData.getAll("articulo_id[]").map(String);
  const cantidades = formData.getAll("cantidad[]").map(String);
  const costos = formData.getAll("costo_unitario[]").map(String);
  return articulos.map((articuloId, i) => ({
    articuloId,
    cantidad: cantidades[i] ?? "",
    costoUnitario: costos[i] ?? "",
  }));
}

function validar(
  proveedorId: string,
  almacenId: string,
  items: ItemForm[],
): string | null {
  if (!proveedorId) return "Elegir un proveedor.";
  if (!almacenId) return "Elegir el almacén de destino.";
  const validos = items.filter((it) => it.articuloId && it.cantidad && it.costoUnitario);
  if (validos.length === 0) return "Agregar al menos un ítem con artículo, cantidad y costo.";
  if (validos.some((it) => Number(it.cantidad) <= 0)) return "La cantidad debe ser mayor a 0.";
  return null;
}

export async function crearOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const proveedorId = String(formData.get("proveedor_id") ?? "");
  const almacenId = String(formData.get("almacen_destino_id") ?? "");
  const items = leerItems(formData).filter(
    (it) => it.articuloId && it.cantidad && it.costoUnitario,
  );

  const errorValidacion = validar(proveedorId, almacenId, items);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/purchases/ordenes-compra", {
      token,
      metodo: "POST",
      cuerpo: {
        proveedor_id: proveedorId,
        almacen_destino_id: almacenId,
        // Client-generada: el backend la usa para no duplicar la OC si el
        // POST se reintenta (doble clic, red inestable).
        idempotency_key: crypto.randomUUID(),
        items: items.map((it) => ({
          articulo_id: it.articuloId,
          cantidad: it.cantidad,
          costo_unitario: it.costoUnitario,
        })),
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear la orden de compra.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/compras/ordenes-compra");
  return { error: "", ok: true };
}

export async function editarOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const ordenId = String(formData.get("orden_id") ?? "");
  if (!ordenId) return { error: "Orden de compra inválida.", ok: false };

  const items = leerItems(formData).filter(
    (it) => it.articuloId && it.cantidad && it.costoUnitario,
  );
  if (items.length === 0) {
    return { error: "Agregar al menos un ítem con artículo, cantidad y costo.", ok: false };
  }
  if (items.some((it) => Number(it.cantidad) <= 0)) {
    return { error: "La cantidad debe ser mayor a 0.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/purchases/ordenes-compra/${ordenId}`, {
      token,
      metodo: "PATCH",
      cuerpo: {
        items: items.map((it) => ({
          articulo_id: it.articuloId,
          cantidad: it.cantidad,
          costo_unitario: it.costoUnitario,
        })),
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo editar la orden de compra.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/compras/ordenes-compra");
  return { error: "", ok: true };
}

/**
 * Las acciones que sacan a la OC de `borrador`.
 *
 * Los cinco endpoints existen y están probados desde el primer slice del
 * módulo; lo que faltaba era quién los llamara. Cada una revalida el listado
 * **y** la ficha: la ficha es la que muestra el estado que acaba de cambiar.
 */
async function ejecutar(
  ruta: string,
  cuerpo: Record<string, unknown> | undefined,
  ordenId: string,
  siFalla: string,
): Promise<EstadoOrdenCompra> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  try {
    await apiFetch(ruta, { token, metodo: "POST", cuerpo });
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : siFalla, ok: false };
  }
  revalidatePath("/compras/ordenes-compra");
  revalidatePath(`/compras/ordenes-compra/${ordenId}`);
  return { error: "", ok: true };
}

export async function emitirOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const ordenId = String(formData.get("orden_id") ?? "");
  if (!ordenId) return { error: "Orden de compra inválida.", ok: false };
  return ejecutar(
    `/api/v1/purchases/ordenes-compra/${ordenId}/emitir`,
    undefined,
    ordenId,
    "No se pudo emitir la orden de compra.",
  );
}

export async function anularOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const ordenId = String(formData.get("orden_id") ?? "");
  if (!ordenId) return { error: "Orden de compra inválida.", ok: false };
  return ejecutar(
    `/api/v1/purchases/ordenes-compra/${ordenId}/anular`,
    undefined,
    ordenId,
    "No se pudo anular la orden de compra.",
  );
}

/** Lo recibido, línea por línea. Una fila sin cantidad es una línea que esta
 * entrega no trajo: se descarta en vez de mandarse en cero, que el servidor
 * rechazaría. */
function leerRecepcion(formData: FormData) {
  const ids = formData.getAll("orden_compra_item_id[]").map(String);
  const cantidades = formData.getAll("cantidad_recibida[]").map(String);
  const costos = formData.getAll("costo_recibido[]").map(String);
  const lotes = formData.getAll("lote_codigo[]").map(String);
  const vencimientos = formData.getAll("fecha_vencimiento[]").map(String);
  return ids
    .map((id, i) => ({
      orden_compra_item_id: id,
      cantidad_recibida: cantidades[i] ?? "",
      costo_unitario: costos[i] || undefined,
      lote_codigo: lotes[i] || undefined,
      fecha_vencimiento: vencimientos[i] || undefined,
    }))
    .filter((it) => it.orden_compra_item_id && Number(it.cantidad_recibida) > 0);
}

export async function recibirOrdenCompraAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const ordenId = String(formData.get("orden_id") ?? "");
  if (!ordenId) return { error: "Orden de compra inválida.", ok: false };

  const items = leerRecepcion(formData);
  if (items.length === 0) {
    return { error: "Indica cuánto llegó de al menos un ítem.", ok: false };
  }
  return ejecutar(
    `/api/v1/purchases/ordenes-compra/${ordenId}/recepciones`,
    { idempotency_key: crypto.randomUUID(), items },
    ordenId,
    "No se pudo registrar la recepción.",
  );
}

export async function registrarFacturaAction(
  _previo: EstadoOrdenCompra,
  formData: FormData,
): Promise<EstadoOrdenCompra> {
  const ordenId = String(formData.get("orden_id") ?? "");
  if (!ordenId) return { error: "Orden de compra inválida.", ok: false };

  const cuerpo = cuerpoDeFactura(formData, crypto.randomUUID());
  const falta = faltaEnLaFactura(cuerpo);
  if (falta) return { error: falta, ok: false };
  return ejecutar(
    `/api/v1/purchases/ordenes-compra/${ordenId}/conformidad-comprobante`,
    cuerpo,
    ordenId,
    "No se pudo registrar la factura.",
  );
}
