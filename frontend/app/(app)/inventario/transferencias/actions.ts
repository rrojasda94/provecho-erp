"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/inventario/transferencias";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/**
 * Recibe una transferencia en tránsito: el stock entra al almacén destino.
 *
 * Cierra el circuito que quedaba abierto por la mitad. El endpoint existía
 * desde el slice de transferencias y ninguna pantalla lo llamaba, así que lo
 * despachado se quedaba `en_transito` para siempre y el solicitante nunca
 * veía llegar su pedido.
 *
 * Sin `items` se recibe todo lo enviado, que es el caso normal; una
 * recepción parcial se declara explícitamente para no dar por perdido lo que
 * todavía viene en camino.
 */
export async function recibirTransferenciaAction(
  transferenciaId: string,
): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/inventory/transferencias/${transferenciaId}/recibir`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { items: [], parcial: false },
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo recibir.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
