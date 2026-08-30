"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoUsuario = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function leerCuenta(formData: FormData) {
  return {
    username: String(formData.get("username") ?? "").trim(),
    pin: String(formData.get("pin") ?? "").trim(),
    tipo: String(formData.get("tipo") ?? "humano"),
    // Se puede vincular desde el alta: antes solo estaba en «Editar cuenta»,
    // así que dar de alta a alguien que iba a marcar asistencia obligaba a
    // crear la cuenta y volver a abrirla para asociarle la persona.
    persona_id: String(formData.get("persona_id") ?? "").trim() || undefined,
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
    return estadoDeError(e, "No se pudo crear la cuenta.");
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
    return estadoDeError(e, "No se pudo cambiar el estado.");
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
        // `null` y no `undefined`: acá vacío SÍ es una acción — desvincular
        // la persona (ADR-070) — y `undefined` se cae del JSON sin mandar
        // nada (`lib/api.ts`), que es "no tocar". El alta (`leerCuenta`)
        // sigue con `undefined`: ahí vacío es "todavía no elegí a nadie".
        persona_id: String(formData.get("persona_id") ?? "").trim() || null,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo guardar la cuenta.");
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
    return estadoDeError(e, "No se pudo asignar el rol.");
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
    return estadoDeError(e, "No se pudo quitar el rol.");
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

/** Suma un local al alcance de la cuenta.
 *
 * Un supervisor a cargo de varias sucursales son varias llamadas a esto: no
 * hay entidad "grupo de sucursales" y no hace falta (ADR-062). El alcance
 * viaja en el token, así que a esa persona le aplica cuando su sesión
 * renueve, no en el acto. */
export async function asignarSucursalAction(
  _previo: EstadoUsuario,
  formData: FormData,
): Promise<EstadoUsuario> {
  const usuarioId = String(formData.get("usuario_id") ?? "");
  const sucursalId = String(formData.get("sucursal_id") ?? "");
  if (!usuarioId || !sucursalId) return { error: "Elegir la sucursal.", ok: false };

  try {
    await apiFetch(`/api/v1/users/${usuarioId}/sucursales`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { sucursal_id: sucursalId },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo asignar la sucursal.");
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

export async function quitarSucursalAction(
  usuarioId: string,
  sucursalId: string,
): Promise<EstadoUsuario> {
  try {
    await apiFetch(`/api/v1/users/${usuarioId}/sucursales/${sucursalId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo quitar la sucursal.");
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}

/**
 * Devuelve la cuenta al PIN por defecto y la obliga a cambiarlo al entrar.
 *
 * Un PIN olvidado no se recupera —está hasheado con Argon2id—, así que la
 * única salida es ponerle uno conocido. Lo que hace que eso sea aceptable
 * pasa del lado del servidor: la cuenta queda marcada y no puede hacer nada
 * más que cambiarlo, se le revocan las sesiones abiertas y queda auditado
 * quién lo hizo.
 */
export async function resetearPinAction(usuarioId: string): Promise<EstadoUsuario> {
  try {
    await apiFetch(`/api/v1/users/${usuarioId}/pin/reset`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo resetear el PIN.");
  }
  revalidatePath("/usuarios");
  return { error: "", ok: true };
}
