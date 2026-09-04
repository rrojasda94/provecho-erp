"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

const RUTA = "/inventario/reservas";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/**
 * Suelta lo prometido a un almacén para poder redistribuirlo (RN-INV-011).
 *
 * Es la salida del callejón: una reserva colgada de un requerimiento que
 * nadie despachó mantiene stock fuera del disponible para siempre, y hasta
 * hoy el permiso `inventory.liberar_reserva` estaba sembrado sin que nadie
 * pudiera ejercerlo desde ninguna pantalla.
 */
export async function liberarReservaAction(reservaId: string): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/inventory/reservas/${reservaId}/liberar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo liberar la reserva.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
