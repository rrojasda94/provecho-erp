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

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/** El código es el que después nombran las reglas de distribución: se escribe
 * una vez y no se edita —el `PATCH` no lo acepta— porque cambiarlo dejaría a
 * las reglas apuntando a un área que ya no se llama así. */
export async function crearAreaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const codigo = texto(formData, "codigo");
  const nombre = texto(formData, "nombre");
  if (!codigo || !nombre) return { error: "Hacen falta el código y el nombre.", ok: false };

  try {
    await apiFetch("/api/v1/reports/areas", {
      token: await token(),
      metodo: "POST",
      cuerpo: { codigo, nombre },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear el área.");
  }
  revalidatePath("/reportes/areas");
  return { error: "", ok: true };
}

export async function editarAreaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const id = texto(formData, "id");
  const nombre = texto(formData, "nombre");
  if (!id) return { error: "Falta el área a editar.", ok: false };
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  try {
    await apiFetch(`/api/v1/reports/areas/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { nombre, activa: formData.get("activa") === "on" },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar el área.");
  }
  revalidatePath("/reportes/areas");
  return { error: "", ok: true };
}

/** Un miembro es **un rol o una persona**, nunca los dos: el rol es «quien
 * ocupe ese puesto» y la persona es esa persona. Mezclarlos en una fila
 * dejaría sin saber cuál manda cuando el puesto cambia de manos. */
export async function agregarMiembroAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const areaId = texto(formData, "area_id");
  const rolId = texto(formData, "rol_id");
  const usuarioId = texto(formData, "usuario_id");
  const sucursalId = texto(formData, "sucursal_id");
  if (!areaId) return { error: "Falta el área.", ok: false };
  if (!rolId && !usuarioId) return { error: "Elegí un rol o una persona.", ok: false };
  if (rolId && usuarioId) {
    return { error: "Un miembro es un rol o una persona, no las dos.", ok: false };
  }

  try {
    await apiFetch(`/api/v1/reports/areas/${areaId}/miembros`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        rol_id: rolId || undefined,
        usuario_id: usuarioId || undefined,
        sucursal_id: sucursalId || undefined,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo agregar el miembro.");
  }
  revalidatePath("/reportes/areas");
  return { error: "", ok: true };
}

export async function quitarMiembroAction(
  areaId: string,
  miembroId: string,
): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/reports/areas/${areaId}/miembros/${miembroId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo quitar el miembro.");
  }
  revalidatePath("/reportes/areas");
  return { error: "", ok: true };
}
