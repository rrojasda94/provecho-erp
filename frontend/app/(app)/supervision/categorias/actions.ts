"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/supervision/categorias";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export type EstadoCategoria = EstadoFormulario;

export async function crearCategoriaAction(
  _previo: EstadoCategoria,
  formData: FormData,
): Promise<EstadoCategoria> {
  const nombre = String(formData.get("nombre") ?? "").trim();
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };
  try {
    await apiFetch("/api/v1/supervision/categorias", {
      token: await token(),
      metodo: "POST",
      cuerpo: { nombre },
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo crear la categoría.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function alternarActivaAction(
  categoriaId: string,
  activa: boolean,
): Promise<{ error: string; ok: boolean }> {
  try {
    await apiFetch(`/api/v1/supervision/categorias/${categoriaId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { activa },
    });
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "No se pudo actualizar.", ok: false };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
