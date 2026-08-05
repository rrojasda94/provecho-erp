"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoVenta = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

export async function anularVentaAction(ventaId: string): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/ventas/${ventaId}/anular`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo anular la venta."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}

export type LineaVenta = {
  id: string;
  nombre: string;
  cantidad: string;
  precio_unitario: string;
  grupo_cobro: number;
};

/** Las líneas se piden al abrir el diálogo, no al pintar la jornada: solo
 * hacen falta para acreditar y traerlas por cada venta del día sería un
 * viaje por fila para algo que casi nunca se usa. */
export async function lineasDeVentaAction(ventaId: string): Promise<LineaVenta[]> {
  try {
    return await apiFetch<LineaVenta[]>(`/api/v1/sales/ventas/${ventaId}/items`, {
      token: await token(),
    });
  } catch {
    return [];
  }
}

export async function emitirNotaCreditoAction(
  _previo: EstadoVenta,
  formData: FormData,
): Promise<EstadoVenta> {
  const comprobanteId = String(formData.get("comprobante_id") ?? "");
  const motivo = String(formData.get("motivo") ?? "");
  const parcial = formData.get("alcance") === "parcial";
  if (!comprobanteId || !motivo) return { error: "Falta el motivo.", ok: false };

  // Las cantidades viajan como filas paralelas; solo entran las > 0, así
  // que dejar una línea en cero equivale a no devolverla.
  const ids = formData.getAll("linea_id").map(String);
  const cantidades = formData.getAll("linea_cantidad").map(String);
  const detalle = ids
    .map((id, i) => ({ venta_item_id: id, cantidad: cantidades[i] ?? "0" }))
    .filter((d) => Number(d.cantidad) > 0);
  if (parcial && detalle.length === 0) {
    return { error: "Una nota parcial necesita al menos una línea.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/sales/comprobantes/${comprobanteId}/nota-credito`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        motivo,
        detalle: parcial ? detalle : undefined,
        repone_stock: formData.get("repone_stock") === "on",
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo emitir la nota de crédito."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}

export async function reintentarComprobanteAction(
  comprobanteId: string,
): Promise<EstadoVenta> {
  try {
    await apiFetch(`/api/v1/sales/comprobantes/${comprobanteId}/reintentar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    // 502 = SUNAT/Factiliza rechazó de nuevo. El intento ya quedó contado en
    // el comprobante, así que la pantalla se recarga igual para mostrarlo.
    revalidatePath("/ventas");
    return { error: mensajeDe(e, "El comprobante volvió a fallar."), ok: false };
  }
  revalidatePath("/ventas");
  return { error: "", ok: true };
}
