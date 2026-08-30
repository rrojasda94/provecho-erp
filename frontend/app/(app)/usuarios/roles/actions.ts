"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoRol = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export async function crearRolAction(
  _previo: EstadoRol,
  formData: FormData,
): Promise<EstadoRol> {
  const nombre = String(formData.get("nombre") ?? "").trim();
  const descripcion = String(formData.get("descripcion") ?? "").trim();
  if (!nombre) return { error: "El rol necesita nombre.", ok: false };

  try {
    await apiFetch("/api/v1/roles", {
      token: await token(),
      metodo: "POST",
      cuerpo: { nombre, descripcion: descripcion || undefined },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear el rol.");
  }
  revalidatePath("/usuarios/roles");
  return { error: "", ok: true };
}

export async function asignarPermisoAction(
  _previo: EstadoRol,
  formData: FormData,
): Promise<EstadoRol> {
  const rolId = String(formData.get("rol_id") ?? "");
  const permisoId = String(formData.get("permiso_id") ?? "");
  if (!rolId || !permisoId) return { error: "Elegir el permiso.", ok: false };

  try {
    await apiFetch(`/api/v1/roles/${rolId}/permisos`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { permiso_id: permisoId },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo asignar el permiso.");
  }
  revalidatePath("/usuarios/roles");
  return { error: "", ok: true };
}

export async function quitarPermisoAction(
  rolId: string,
  permisoId: string,
): Promise<EstadoRol> {
  try {
    await apiFetch(`/api/v1/roles/${rolId}/permisos/${permisoId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo quitar el permiso.");
  }
  revalidatePath("/usuarios/roles");
  return { error: "", ok: true };
}
