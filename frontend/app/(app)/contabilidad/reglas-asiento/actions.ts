"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError, type EstadoFormulario } from "@/lib/errores";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

/** `POST /accounting/reglas-asiento` existía desde el slice del libro
 * contable y no lo llamaba ninguna pantalla: el mapeo evento→cuentas solo se
 * podía configurar llamando la API a mano. */
export async function crearReglaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const evento = String(formData.get("evento") ?? "").trim();
  const cuentaDebe = String(formData.get("cuenta_debe_id") ?? "");
  const cuentaHaber = String(formData.get("cuenta_haber_id") ?? "");
  if (!evento) return { error: "Elegí el hecho que se va a asentar.", ok: false };
  if (!cuentaDebe || !cuentaHaber) {
    return { error: "Hacen falta las dos cuentas: la del debe y la del haber.", ok: false };
  }
  if (cuentaDebe === cuentaHaber) {
    return {
      error: "El debe y el haber no pueden ser la misma cuenta: el asiento no diría nada.",
      ok: false,
    };
  }

  try {
    await apiFetch("/api/v1/accounting/reglas-asiento", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        evento,
        cuenta_debe_id: cuentaDebe,
        cuenta_haber_id: cuentaHaber,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear la regla.");
  }
  revalidatePath("/contabilidad/reglas-asiento");
  return { error: "", ok: true };
}
