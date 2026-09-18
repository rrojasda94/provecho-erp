"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiAuth } from "@/lib/api";
import { COOKIE_REFRESH, COOKIE_TOKEN, opcionesCookie } from "@/lib/auth";
import type { Estado } from "@/lib/estado-formulario";

type Tokens = { access_token: string; refresh_token: string };

async function guardarSesion(tokens: Tokens): Promise<void> {
  const store = await cookies();
  store.set(COOKIE_TOKEN, tokens.access_token, opcionesCookie());
  store.set(COOKIE_REFRESH, tokens.refresh_token, opcionesCookie());
}

function mensajeDeError(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

export async function registrarAction(_previo: Estado, formData: FormData): Promise<Estado> {
  try {
    const tokens = await apiAuth<Tokens>("/api/v1/storefront/cuentas/registro", {
      metodo: "POST",
      cuerpo: {
        email: texto(formData, "email"),
        password: texto(formData, "password"),
        nombres: texto(formData, "nombres"),
        apellidos: texto(formData, "apellidos"),
        tipo_documento: "dni",
        numero_documento: texto(formData, "numero_documento"),
        telefono: texto(formData, "telefono"),
        fecha_nacimiento: texto(formData, "fecha_nacimiento"),
        direccion: texto(formData, "direccion") || undefined,
      },
    });
    await guardarSesion(tokens);
  } catch (e) {
    return { error: mensajeDeError(e, "No se pudo crear la cuenta."), ok: false };
  }
  redirect("/cuenta");
}

export async function loginAction(_previo: Estado, formData: FormData): Promise<Estado> {
  try {
    const tokens = await apiAuth<Tokens>("/api/v1/storefront/cuentas/login", {
      metodo: "POST",
      cuerpo: { email: texto(formData, "email"), password: texto(formData, "password") },
    });
    await guardarSesion(tokens);
  } catch (e) {
    return { error: mensajeDeError(e, "No se pudo iniciar sesión."), ok: false };
  }
  redirect("/cuenta");
}

/** Llamado desde el botón de Google (`GoogleLoginButton`, client component)
 * tras recibir el `credential` del SDK de Identity Services. Los campos de
 * perfil solo importan la primera vez (cuenta nueva, RN-WEB-005); en los
 * siguientes logins el backend los ignora. */
export async function loginGoogleAction(datos: {
  idToken: string;
  nombres?: string;
  apellidos?: string;
  numeroDocumento?: string;
  telefono?: string;
  fechaNacimiento?: string;
  direccion?: string;
}): Promise<Estado> {
  try {
    const tokens = await apiAuth<Tokens>("/api/v1/storefront/cuentas/google", {
      metodo: "POST",
      cuerpo: {
        id_token: datos.idToken,
        nombres: datos.nombres || undefined,
        apellidos: datos.apellidos || undefined,
        tipo_documento: datos.numeroDocumento ? "dni" : undefined,
        numero_documento: datos.numeroDocumento || undefined,
        telefono: datos.telefono || undefined,
        fecha_nacimiento: datos.fechaNacimiento || undefined,
        direccion: datos.direccion || undefined,
      },
    });
    await guardarSesion(tokens);
  } catch (e) {
    return { error: mensajeDeError(e, "No se pudo continuar con Google."), ok: false };
  }
  redirect("/cuenta");
}

export async function logoutAction(): Promise<void> {
  const store = await cookies();
  const refresh = store.get(COOKIE_REFRESH)?.value;
  if (refresh) {
    try {
      await apiAuth("/api/v1/storefront/cuentas/logout", {
        metodo: "POST",
        cuerpo: { refresh_token: refresh },
      });
    } catch {
      // Ya se va a borrar la cookie igual: que la API no conteste no
      // puede dejar a alguien atrapado en su propia sesión.
    }
  }
  store.delete(COOKIE_TOKEN);
  store.delete(COOKIE_REFRESH);
  redirect("/");
}

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/cuenta/ingresar");
  return valor;
}

export async function agregarDireccionAction(_previo: Estado, formData: FormData): Promise<Estado> {
  try {
    await apiAuth("/api/v1/storefront/cuentas/me/direcciones", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        etiqueta: texto(formData, "etiqueta") || undefined,
        direccion: texto(formData, "direccion"),
        referencia: texto(formData, "referencia") || undefined,
        predeterminada: formData.get("predeterminada") === "on",
      },
    });
  } catch (e) {
    return { error: mensajeDeError(e, "No se pudo guardar la dirección."), ok: false };
  }
  return { error: "", ok: true };
}

export async function borrarDireccionAction(direccionId: string): Promise<void> {
  await apiAuth(`/api/v1/storefront/cuentas/me/direcciones/${direccionId}`, {
    token: await token(),
    metodo: "DELETE",
  });
}

export async function agregarFavoritoAction(productoComercialId: string): Promise<void> {
  await apiAuth("/api/v1/storefront/cuentas/me/favoritos", {
    token: await token(),
    metodo: "POST",
    cuerpo: { producto_comercial_id: productoComercialId },
  });
}

export async function quitarFavoritoAction(productoComercialId: string): Promise<void> {
  await apiAuth(`/api/v1/storefront/cuentas/me/favoritos/${productoComercialId}`, {
    token: await token(),
    metodo: "DELETE",
  });
}
