"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export async function generarInformeAction(
  sucursalId: string,
  fecha: string,
): Promise<{ error: string; ok: boolean }> {
  try {
    await apiFetch(
      `/api/v1/supervision/informes/generar?sucursal_id=${sucursalId}&fecha=${fecha}`,
      { token: await token(), metodo: "POST" },
    );
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "No se pudo generar.", ok: false };
  }
  revalidatePath("/supervision/informes");
  return { error: "", ok: true };
}
