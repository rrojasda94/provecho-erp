"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/activos/documentos";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

export async function crearDocumentoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const sujetoId = texto(formData, "sujeto_id");
  const tipoDocumento = texto(formData, "tipo_documento");
  const fechaVencimiento = texto(formData, "fecha_vencimiento");
  if (!sujetoId || !tipoDocumento || !fechaVencimiento) {
    return { error: "Sujeto, tipo de documento y fecha de vencimiento son obligatorios.", ok: false };
  }

  try {
    await apiFetch("/api/v1/assets/documentos", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        sujeto_tipo: String(formData.get("sujeto_tipo") ?? "activo"),
        sujeto_id: sujetoId,
        tipo_documento: tipoDocumento,
        fecha_vencimiento: fechaVencimiento,
        numero: texto(formData, "numero") || undefined,
        emisor: texto(formData, "emisor") || undefined,
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el documento.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function renovarDocumentoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const documentoId = texto(formData, "documento_id");
  const fechaVencimiento = texto(formData, "fecha_vencimiento");
  if (!fechaVencimiento) return { error: "La nueva fecha de vencimiento es obligatoria.", ok: false };

  try {
    await apiFetch(`/api/v1/assets/documentos/${documentoId}/renovar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { fecha_vencimiento: fechaVencimiento, numero: texto(formData, "numero") || undefined },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo renovar el documento.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
