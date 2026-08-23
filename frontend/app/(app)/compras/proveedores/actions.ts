"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { ubicacionDe } from "@/lib/ubicacion-form";

export type EstadoProveedor = EstadoFormulario;

const RUTA = "/compras/proveedores";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

type DatosProveedor = {
  tipo: string;
  personaId: string;
  razonSocial: string;
  ruc: string;
  condicionPago: string;
  plazoDias: string;
};

function leerFormulario(formData: FormData): DatosProveedor {
  return {
    tipo: String(formData.get("tipo") ?? "juridico"),
    personaId: texto(formData, "persona_id"),
    razonSocial: texto(formData, "razon_social"),
    ruc: texto(formData, "ruc"),
    condicionPago: String(formData.get("condicion_pago") ?? "contado"),
    plazoDias: texto(formData, "plazo_dias_credito"),
  };
}

function validarIdentificacion(datos: DatosProveedor): string | null {
  if (!datos.razonSocial || !datos.ruc) return "Razón social y RUC son obligatorios.";
  if (datos.ruc.length !== 11) return "El RUC debe tener 11 dígitos.";
  return null;
}

function validarCondicionPago(datos: DatosProveedor): string | null {
  return datos.condicionPago === "credito" && !datos.plazoDias
    ? "Crédito exige un plazo de días."
    : null;
}

function validar(datos: DatosProveedor): string | null {
  const identificacion =
    datos.tipo === "natural"
      ? datos.personaId
        ? null
        : "Elegir la persona."
      : validarIdentificacion(datos);
  return identificacion ?? validarCondicionPago(datos);
}

/** El domicilio fiscal es del proveedor **jurídico**: el natural lo tiene en
 * su persona (RN-GEN-007) y ahí se corrige. */
function domicilio(formData: FormData) {
  return {
    direccion: texto(formData, "direccion") || undefined,
    provincia: texto(formData, "provincia") || undefined,
    pais: texto(formData, "pais") || undefined,
    ...ubicacionDe(formData),
  };
}

function cuerpoAlta(formData: FormData, datos: DatosProveedor) {
  const esJuridico = datos.tipo === "juridico";
  return {
    tipo: datos.tipo,
    persona_id: esJuridico ? undefined : datos.personaId,
    razon_social: esJuridico ? datos.razonSocial : undefined,
    ruc: esJuridico ? datos.ruc : undefined,
    ...(esJuridico ? domicilio(formData) : {}),
    condicion_pago: datos.condicionPago,
    plazo_dias_credito:
      datos.condicionPago === "credito" ? Number(datos.plazoDias) : undefined,
  };
}

export async function crearProveedorAction(
  _previo: EstadoProveedor,
  formData: FormData,
): Promise<EstadoProveedor> {
  const datos = leerFormulario(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/purchases/proveedores", {
      token: await token(),
      metodo: "POST",
      cuerpo: cuerpoAlta(formData, datos),
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el proveedor.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** El diálogo de un proveedor natural ni dibuja razón social ni RUC: que el
 * formulario los traiga es la señal de que hay identificación que corregir.
 * Mandarlos vacíos sería pedirle al servidor que los borre. */
function corrigeIdentificacion(formData: FormData): boolean {
  return formData.has("ruc");
}

function cuerpoEdicion(formData: FormData, datos: DatosProveedor) {
  return {
    ...(corrigeIdentificacion(formData)
      ? {
          razon_social: datos.razonSocial,
          ruc: datos.ruc,
          ...domicilio(formData),
        }
      : {}),
    contacto: texto(formData, "contacto") || undefined,
    clasificacion: String(formData.get("clasificacion") ?? "regular"),
    condicion_pago: datos.condicionPago,
    plazo_dias_credito: datos.plazoDias ? Number(datos.plazoDias) : undefined,
    activo: formData.get("activo") === "on",
  };
}

function validarEdicion(formData: FormData, datos: DatosProveedor): string | null {
  const identificacion = corrigeIdentificacion(formData)
    ? validarIdentificacion(datos)
    : null;
  return identificacion ?? validarCondicionPago(datos);
}

/** Corrección de un proveedor existente. */
export async function editarProveedorAction(
  _previo: EstadoProveedor,
  formData: FormData,
): Promise<EstadoProveedor> {
  const id = texto(formData, "id");
  if (!id) return { error: "Falta el proveedor a editar.", ok: false };

  const datos = leerFormulario(formData);
  const errorValidacion = validarEdicion(formData, datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch(`/api/v1/purchases/proveedores/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: cuerpoEdicion(formData, datos),
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo guardar el proveedor.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
