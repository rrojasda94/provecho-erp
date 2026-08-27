"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { ubicacionDe } from "@/lib/ubicacion-form";

export type EstadoCliente = EstadoFormulario;

const RUTA = "/ventas/clientes";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

/** Corrección de un cliente **jurídico**: razón social, RUC y contacto.
 *
 * Un natural no pasa por acá — sus datos viven en su `persona`
 * (RN-GEN-007) y la pantalla lo manda a Usuarios → Personas. */
export async function editarClienteAction(
  _previo: EstadoCliente,
  formData: FormData,
): Promise<EstadoCliente> {
  const id = texto(formData, "id");
  const razonSocial = texto(formData, "razon_social");
  const ruc = texto(formData, "ruc");
  if (!id) return { error: "Falta el cliente a editar.", ok: false };
  if (!razonSocial) return { error: "La razón social es obligatoria.", ok: false };
  if (ruc.length !== 11) return { error: "El RUC debe tener 11 dígitos.", ok: false };

  try {
    await apiFetch(`/api/v1/sales/clientes/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        razon_social: razonSocial,
        ruc,
        contacto: texto(formData, "contacto") || undefined,
        direccion: texto(formData, "direccion") || undefined,
        ...ubicacionDe(formData),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar el cliente."), ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Completar el documento de un natural que se registró solo por teléfono.
 *
 * Endpoint aparte del PATCH general porque aplica las reglas de
 * identificación: desde que lo tiene, el cliente cuenta como identificado
 * para promociones (RN-PTS-002). */
export async function completarDocumentoAction(
  _previo: EstadoCliente,
  formData: FormData,
): Promise<EstadoCliente> {
  const id = texto(formData, "id");
  const documento = texto(formData, "numero_documento");
  if (!id) return { error: "Falta el cliente.", ok: false };
  if (documento.length !== 8 && documento.length !== 11) {
    return { error: "El documento son 8 dígitos (DNI) u 11 (RUC).", ok: false };
  }

  try {
    await apiFetch(`/api/v1/sales/clientes/${id}/documento`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        numero_documento: documento,
        tipo_documento: String(formData.get("tipo_documento") ?? "dni"),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo registrar el documento."), ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
