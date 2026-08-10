"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoUsuario = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

function leerCuenta(formData: FormData) {
  return {
    username: String(formData.get("username") ?? "").trim(),
    pin: String(formData.get("pin") ?? "").trim(),
    tipo: String(formData.get("tipo") ?? "humano"),
    nombre_display: String(formData.get("nombre_display") ?? "").trim() || undefined,
    email: String(formData.get("email") ?? "").trim() || undefined,
  };
}

export async function crearUsuarioAction(
  _previo: EstadoUsuario,
  formData: FormData,
): Promise<EstadoUsuario> {
  const cuenta = leerCuenta(formData);

  if (cuenta.username.length < 3) {
    return { error: "El usuario necesita 3 caracteres o más.", ok: false };
  }
  // El largo real del PIN lo valida el backend (RN de seguridad); acá solo
  // se evita el viaje obvio.
  if (!/^\d{4,}$/.test(cuenta.pin)) {
    return { error: "El PIN son solo dígitos, mínimo 4.", ok: false };
  }

  try {
    await apiFetch("/api/v1/users", {
      token: await token(),
      metodo: "POST",
      cuerpo: cuenta,
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la cuenta."), ok: false };
  }

  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

export async function cambiarActivoAction(
  usuarioId: string,
  activo: boolean,
): Promise<EstadoUsuario> {
  try {
    await apiFetch(`/api/v1/users/${usuarioId}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { activo },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo cambiar el estado."), ok: false };
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

/** Corrige los datos de la cuenta. El `username` no está: es la identidad
 * con la que se firma cada acción del ERP y con la que quedó escrita en el
 * `audit_log` — cambiarlo dejaría el rastro apuntando a un nombre que ya no
 * existe. Una cuenta con el usuario equivocado se desactiva y se crea otra.
 * El PIN tampoco: lo cambia su dueño con su propia sesión. */
export async function editarUsuarioAction(
  _previo: EstadoUsuario,
  formData: FormData,
): Promise<EstadoUsuario> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { error: "Falta la cuenta a editar.", ok: false };

  try {
    await apiFetch(`/api/v1/users/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        nombre_display: String(formData.get("nombre_display") ?? "").trim() || undefined,
        email: String(formData.get("email") ?? "").trim() || undefined,
        persona_id: String(formData.get("persona_id") ?? "") || undefined,
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar la cuenta."), ok: false };
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

export async function asignarRolAction(
  _previo: EstadoUsuario,
  formData: FormData,
): Promise<EstadoUsuario> {
  const usuarioId = String(formData.get("usuario_id") ?? "");
  const rolId = String(formData.get("rol_id") ?? "");
  if (!usuarioId || !rolId) return { error: "Elegir el rol.", ok: false };

  try {
    await apiFetch(`/api/v1/users/${usuarioId}/roles`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { rol_id: rolId },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo asignar el rol."), ok: false };
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

export async function quitarRolAction(
  usuarioId: string,
  rolId: string,
): Promise<EstadoUsuario> {
  try {
    await apiFetch(`/api/v1/users/${usuarioId}/roles/${rolId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo quitar el rol."), ok: false };
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}
