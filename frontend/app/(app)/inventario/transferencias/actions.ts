"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

const RUTA = "/inventario/transferencias";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/**
 * Recibe una transferencia en tránsito: el stock entra al almacén destino.
 *
 * Cierra el circuito que quedaba abierto por la mitad. El endpoint existía
 * desde el slice de transferencias y ninguna pantalla lo llamaba, así que lo
 * despachado se quedaba `en_transito` para siempre y el solicitante nunca
 * veía llegar su pedido.
 *
 * Las cantidades viajan como filas paralelas (`item_id[]`, `cantidad[]`),
 * mismo patrón que la recepción de una orden de compra. `parcial` es
 * explícito y no deducido de que falten ítems: un olvido cerraría la
 * transferencia dando por perdido lo que todavía viene en camino.
 */
export async function recibirTransferenciaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const transferenciaId = texto(formData, "transferencia_id");
  if (!transferenciaId) return { error: "Falta la transferencia.", ok: false };

  const ids = formData.getAll("item_id").map(String);
  const cantidades = formData.getAll("cantidad").map(String);
  const items = ids
    .map((item_id, i) => ({ item_id, cantidad: cantidades[i] ?? "0" }))
    .filter((it) => it.item_id);

  try {
    await apiFetch(`/api/v1/inventory/transferencias/${transferenciaId}/recibir`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { items, parcial: formData.get("parcial") === "on" },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo recibir el traslado.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/**
 * Traslado lateral: de un almacén a otro sin requerimiento previo.
 *
 * El backend lo contempla desde el slice original —`solicitud_id` es
 * opcional y sin él los ítems son obligatorios— y no había por dónde
 * crearlo: la única llamada a `POST /transferencias` salía del despacho de
 * un requerimiento aprobado. Es el caso de la sucursal que le presta harina
 * a la de al lado, que hasta hoy se resolvía sin registrar nada.
 */
export async function trasladoDirectoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const origen = texto(formData, "origen_almacen_id");
  const destino = texto(formData, "destino_almacen_id");
  if (!origen || !destino) return { error: "Elige los dos almacenes.", ok: false };
  if (origen === destino) {
    return { error: "El origen y el destino no pueden ser el mismo almacén.", ok: false };
  }

  const skus = formData.getAll("sku_id").map(String);
  const cantidades = formData.getAll("cantidad").map(String);
  const items = skus
    .map((sku_id, i) => ({ sku_id, cantidad: cantidades[i] ?? "" }))
    .filter((it) => it.sku_id && Number(it.cantidad) > 0);
  if (items.length === 0) {
    return { error: "Agrega al menos un artículo con cantidad.", ok: false };
  }

  try {
    await apiFetch("/api/v1/inventory/transferencias", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        origen_almacen_id: origen,
        destino_almacen_id: destino,
        items,
        observacion: texto(formData, "observacion") || null,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo despachar el traslado.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
