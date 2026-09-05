"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError, type EstadoFormulario } from "@/lib/errores";
import { obtenerSesion } from "@/lib/sesion";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/** Quién firma la sanción sale de la sesión, no del formulario: el emisor es
 * quien la está emitiendo, y dejarlo elegir sería poder firmar por otro — que
 * es exactamente lo que un descargo va a discutir (RN-RRHH-002). */
async function emisor(): Promise<string> {
  const { usuario } = await obtenerSesion();
  return usuario.id;
}

export async function emitirAmonestacionAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const trabajadorId = texto(formData, "trabajador_id");
  const tipo = texto(formData, "tipo");
  const falta = texto(formData, "falta");
  const fechaHecho = texto(formData, "fecha_hecho");
  const fechaEmision = texto(formData, "fecha_emision");
  if (!falta) {
    return { error: "Falta describir la falta: sin eso no se puede descargar.", ok: false };
  }
  if (!fechaHecho || !fechaEmision) {
    return { error: "Hacen falta la fecha del hecho y la de emisión.", ok: false };
  }

  try {
    await apiFetch("/api/v1/rrhh/amonestaciones", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        trabajador_id: trabajadorId,
        tipo,
        falta,
        fecha_hecho: fechaHecho,
        fecha_emision: fechaEmision,
        emisor_id: await emisor(),
        descargo_plazo_dias: Number(formData.get("descargo_plazo_dias") ?? 0) || undefined,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo emitir la amonestación.");
  }
  revalidatePath(`/rrhh/trabajadores/${trabajadorId}`);
  return { error: "", ok: true };
}

export async function emitirMemorandumAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const trabajadorId = String(formData.get("trabajador_id") ?? "");
  const asunto = String(formData.get("asunto") ?? "").trim();
  const cuerpo = String(formData.get("cuerpo") ?? "").trim();
  const fecha = String(formData.get("fecha") ?? "");
  if (!asunto || !cuerpo) return { error: "Un memorándum lleva asunto y cuerpo.", ok: false };
  if (!fecha) return { error: "Falta la fecha.", ok: false };

  try {
    await apiFetch("/api/v1/rrhh/memorandums", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        emisor_id: await emisor(),
        asunto,
        cuerpo,
        fecha,
        destinatario_trabajador_id: trabajadorId,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo emitir el memorándum.");
  }
  revalidatePath(`/rrhh/trabajadores/${trabajadorId}`);
  return { error: "", ok: true };
}

/** El tiempo de servicios y si sale dentro de plazo los calcula el servidor
 * (RN-RRHH-007): son la razón de ser del documento y no se teclean. */
export async function emitirCertificadoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const trabajadorId = String(formData.get("trabajador_id") ?? "");
  const cargos = String(formData.get("cargos") ?? "").trim();
  const fechaEmision = String(formData.get("fecha_emision") ?? "");
  if (!cargos) return { error: "Falta el cargo o los cargos que ocupó.", ok: false };
  if (!fechaEmision) return { error: "Falta la fecha de emisión.", ok: false };

  try {
    await apiFetch("/api/v1/rrhh/certificados-trabajo", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        trabajador_id: trabajadorId,
        fecha_emision: fechaEmision,
        cargos,
        conducta_desempeno: String(formData.get("conducta_desempeno") ?? "").trim() || undefined,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo emitir el certificado.");
  }
  revalidatePath(`/rrhh/trabajadores/${trabajadorId}`);
  return { error: "", ok: true };
}
