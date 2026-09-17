"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/supervision/tablero";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export type EstadoTablero = EstadoFormulario;

export async function crearTareaManualAction(
  _previo: EstadoTablero,
  formData: FormData,
): Promise<EstadoTablero> {
  const checklist = String(formData.get("checklist") ?? "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  try {
    await apiFetch("/api/v1/supervision/tareas", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        sucursal_id: formData.get("sucursal_id"),
        fecha: formData.get("fecha"),
        momento: formData.get("momento"),
        categoria_id: formData.get("categoria_id"),
        nombre: formData.get("nombre"),
        requiere_foto: formData.get("requiere_foto") === "on",
        checklist,
      },
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo crear la tarea.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function asignarAction(
  instanciaId: string,
  usuarioId: string,
): Promise<{ error: string; ok: boolean }> {
  try {
    await apiFetch(`/api/v1/supervision/tareas/${instanciaId}/asignar`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { usuario_id: usuarioId },
    });
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "No se pudo asignar.", ok: false };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function generarDiaAction(
  fecha: string,
): Promise<{ error: string; ok: boolean; generadas?: number }> {
  try {
    const r = await apiFetch<{ generadas: number }>(
      `/api/v1/supervision/tareas/generar?fecha=${fecha}`,
      { token: await token(), metodo: "POST" },
    );
    revalidatePath(RUTA);
    return { error: "", ok: true, generadas: r.generadas };
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "No se pudo generar.", ok: false };
  }
}
