"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_INTERNAL_URL, ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { leerError } from "@/lib/errores";

const RUTA = "/supervision/mis-tareas";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export type ResultadoAccion = { error: string; ok: boolean };

export async function marcarItemAction(
  instanciaId: string,
  indice: number,
  hecho: boolean,
): Promise<ResultadoAccion> {
  try {
    await apiFetch(`/api/v1/supervision/tareas/${instanciaId}/checklist/${indice}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { hecho },
    });
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "No se pudo marcar el ítem.", ok: false };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Sube la foto directo con `fetch` y no con `apiFetch`: la evidencia viaja
 * multipart y `apiFetch` siempre serializa el cuerpo a JSON. */
export async function subirFotoAction(
  instanciaId: string,
  formData: FormData,
): Promise<ResultadoAccion> {
  const archivo = formData.get("archivo");
  if (!(archivo instanceof File) || archivo.size === 0) {
    return { error: "Elige una foto.", ok: false };
  }
  const cuerpo = new FormData();
  cuerpo.set("archivo", archivo);

  const respuesta = await fetch(
    `${API_INTERNAL_URL}/api/v1/supervision/tareas/${instanciaId}/foto`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${await token()}` },
      body: cuerpo,
      cache: "no-store",
    },
  );
  if (!respuesta.ok) {
    const { mensaje } = await leerError(respuesta);
    return { error: mensaje, ok: false };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function completarAction(
  instanciaId: string,
  observacion: string,
): Promise<ResultadoAccion> {
  try {
    await apiFetch(`/api/v1/supervision/tareas/${instanciaId}/completar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { observacion: observacion || undefined },
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo completar la tarea.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
