"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoOrdenHija = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export async function crearOrdenHijaAction(
  _previo: EstadoOrdenHija,
  formData: FormData,
): Promise<EstadoOrdenHija> {
  const ordenId = String(formData.get("orden_id") ?? "");
  const articuloId = String(formData.get("articulo_id") ?? "");
  const cantidad = String(formData.get("cantidad_planeada") ?? "");
  if (!ordenId || !articuloId) return { error: "Falta el artículo a fabricar.", ok: false };
  if (Number(cantidad) <= 0) return { error: "La cantidad planeada debe ser > 0.", ok: false };

  try {
    await apiFetch(`/api/v1/production/ordenes/${ordenId}/ordenes-hijas`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        articulo_id: articuloId,
        cantidad_planeada: cantidad,
        // Client-generada: un reintento de red no duplica la orden hija.
        idempotency_key: `op-hija-${crypto.randomUUID()}`,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear la orden hija.");
  }
  revalidatePath(`/produccion/ordenes/${ordenId}`);
  return { error: "", ok: true };
}
