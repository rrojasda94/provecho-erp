"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoPersona = EstadoFormulario;

const RUTA = "/usuarios/personas";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/** Los campos que la persona comparte entre alta y corrección. Fecha de
 * nacimiento, domicilio, teléfono y email van sin valor cuando están vacíos:
 * en el PATCH `null` significa "no tocar", no "borrar". */
function datosComunes(formData: FormData) {
  return {
    nombres: texto(formData, "nombres"),
    apellidos: texto(formData, "apellidos"),
    tipo_documento: String(formData.get("tipo_documento") ?? "dni"),
    numero_documento: texto(formData, "numero_documento"),
    fecha_nacimiento: texto(formData, "fecha_nacimiento") || undefined,
    domicilio: texto(formData, "domicilio") || undefined,
    telefono: texto(formData, "telefono") || undefined,
    email: texto(formData, "email") || undefined,
  };
}

function validar(datos: ReturnType<typeof datosComunes>): string | null {
  if (!datos.nombres || !datos.apellidos) return "Nombres y apellidos son obligatorios.";
  if (!datos.numero_documento) return "El número de documento es obligatorio.";
  return null;
}

export async function crearPersonaAction(
  _previo: EstadoPersona,
  formData: FormData,
): Promise<EstadoPersona> {
  const datos = datosComunes(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/personas", {
      token: await token(),
      metodo: "POST",
      cuerpo: datos,
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear la persona.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/**
 * Rectificación de una persona (derecho ARCO, Ley 29733 — ADR-011). Hasta
 * ahora solo se ejercía por `curl`.
 *
 * Manda la `version` que se leyó: si otro administrador guardó primero, la
 * API responde 409 y ese mensaje se muestra tal cual. Sin el bloqueo
 * optimista el segundo en guardar pisaba al primero en silencio, que sobre
 * datos personales significa "el domicilio corregido volvió al viejo y nadie
 * se enteró".
 */
export async function editarPersonaAction(
  _previo: EstadoPersona,
  formData: FormData,
): Promise<EstadoPersona> {
  const id = texto(formData, "id");
  const version = texto(formData, "version");
  if (!id || !version) return { error: "Falta la persona a editar.", ok: false };

  const datos = datosComunes(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch(`/api/v1/personas/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { version: Number(version), ...datos },
    });
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      return {
        error: `${e.message}. Alguien más editó esta ficha: recargá la página antes de volver a guardar.`,
        ok: false,
      };
    }
    const mensaje = e instanceof ApiError ? e.message : "No se pudo guardar la persona.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
