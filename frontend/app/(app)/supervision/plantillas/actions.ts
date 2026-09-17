"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/supervision/plantillas";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export type EstadoPlantilla = EstadoFormulario;

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

function checklistDe(formData: FormData): string[] {
  return texto(formData, "checklist")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

function validarFrecuencia(formData: FormData): string | null {
  const frecuencia = texto(formData, "frecuencia");
  if (frecuencia === "semanal" && !texto(formData, "dia_semana")) {
    return "La frecuencia semanal necesita el día de la semana.";
  }
  if (frecuencia === "mensual" && !texto(formData, "dia_mes")) {
    return "La frecuencia mensual necesita el día del mes.";
  }
  return null;
}

function cuerpoPlantilla(formData: FormData, checklist: string[]) {
  const alcance = texto(formData, "alcance"); // "sucursal" | "marca"
  const diaSemana = texto(formData, "dia_semana");
  const diaMes = texto(formData, "dia_mes");
  return {
    sucursal_id: alcance === "sucursal" ? texto(formData, "sucursal_id") : undefined,
    marca_id: alcance === "marca" ? texto(formData, "marca_id") : undefined,
    categoria_id: texto(formData, "categoria_id"),
    nombre: texto(formData, "nombre"),
    descripcion: texto(formData, "descripcion") || undefined,
    momento: texto(formData, "momento"),
    orden: Number(texto(formData, "orden") || "1"),
    frecuencia: texto(formData, "frecuencia"),
    dia_semana: diaSemana ? Number(diaSemana) : undefined,
    dia_mes: diaMes ? Number(diaMes) : undefined,
    fecha_inicio: texto(formData, "fecha_inicio"),
    requiere_foto: formData.get("requiere_foto") === "on",
    checklist,
    asignado_a: texto(formData, "asignado_a") || undefined,
  };
}

export async function crearPlantillaAction(
  _previo: EstadoPlantilla,
  formData: FormData,
): Promise<EstadoPlantilla> {
  const checklist = checklistDe(formData);
  if (checklist.length === 0) {
    return { error: "El checklist necesita al menos un ítem.", ok: false };
  }
  const errorFrecuencia = validarFrecuencia(formData);
  if (errorFrecuencia) return { error: errorFrecuencia, ok: false };

  try {
    await apiFetch("/api/v1/supervision/plantillas", {
      token: await token(),
      metodo: "POST",
      cuerpo: cuerpoPlantilla(formData, checklist),
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo crear la plantilla.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

export async function desactivarPlantillaAction(
  plantillaId: string,
): Promise<{ error: string; ok: boolean }> {
  try {
    await apiFetch(`/api/v1/supervision/plantillas/${plantillaId}`, {
      token: await token(),
      metodo: "DELETE",
    });
  } catch (e) {
    return {
      error: e instanceof ApiError ? e.message : "No se pudo desactivar la plantilla.",
      ok: false,
    };
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
