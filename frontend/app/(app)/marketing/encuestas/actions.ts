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

/** Cierra una encuesta que quedó abierta: el cliente no va a contestar y
 * dejarla «enviada» para siempre ensucia cualquier tasa de respuesta. */
export async function expirarEncuestaAction(id: string): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/marketing/encuestas/${id}/expiracion`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo cerrar la encuesta.");
  }
  revalidatePath("/marketing/encuestas");
  return { error: "", ok: true };
}
