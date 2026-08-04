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
