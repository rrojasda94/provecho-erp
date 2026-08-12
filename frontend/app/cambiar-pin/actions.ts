"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoPin = EstadoFormulario;

const texto = (formData: FormData, campo: string) =>
  String(formData.get(campo) ?? "").trim();

/** Lo que se puede decir sin preguntarle al servidor. La repetición se
 * compara acá porque es un error de tipeo, no una regla de negocio, y el
 * servidor no tiene por qué recibir dos veces el mismo secreto. */
function revisar(actual: string, nuevo: string, repetido: string): string | null {
  if (!actual || !nuevo) return "Faltan datos.";
  if (nuevo !== repetido) return "Los dos PIN nuevos no coinciden.";
  return null;
}

export async function cambiarPinPropioAction(
  _previo: EstadoPin,
  formData: FormData,
): Promise<EstadoPin> {
  const actual = texto(formData, "pin_actual");
  const nuevo = texto(formData, "pin_nuevo");

  const problema = revisar(actual, nuevo, texto(formData, "pin_repetido"));
  if (problema) return { error: problema, ok: false };

  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  try {
    await apiFetch("/api/v1/users/me/pin", {
      token,
      metodo: "POST",
      cuerpo: { pin_actual: actual, pin_nuevo: nuevo },
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo cambiar el PIN.",
      ok: false,
    };
  }
  return { error: "", ok: true };
}
