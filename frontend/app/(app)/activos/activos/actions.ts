"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/activos/activos";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

type DatosActivo = { tipo: string; idInterno: string; nombre: string };

function leerFormulario(formData: FormData): DatosActivo {
  return {
    tipo: String(formData.get("tipo") ?? "equipamiento"),
    idInterno: texto(formData, "id_interno"),
    nombre: texto(formData, "nombre"),
  };
}

function validar(formData: FormData, datos: DatosActivo): string | null {
  if (!datos.idInterno || !datos.nombre) return "ID interno y nombre son obligatorios.";
  if (datos.tipo === "vehiculo" && (!texto(formData, "placa") || !formData.get("tipo_vehiculo"))) {
    return "Un vehículo requiere placa y tipo de vehículo.";
  }
  return null;
}

/** Campos propios de un vehículo — solo se mandan si `tipo === "vehiculo"`. */
function camposVehiculo(formData: FormData) {
  return {
    placa: texto(formData, "placa"),
    tipo_vehiculo: String(formData.get("tipo_vehiculo")),
    numero_motor: texto(formData, "numero_motor") || undefined,
    numero_chasis: texto(formData, "numero_chasis") || undefined,
    tenencia: String(formData.get("tenencia") ?? "propio"),
    kilometraje_inicial: texto(formData, "kilometraje_inicial")
      ? Number(texto(formData, "kilometraje_inicial"))
      : undefined,
  };
}

function cuerpoAlta(formData: FormData, datos: DatosActivo) {
  return {
    tipo: datos.tipo,
    id_interno: datos.idInterno,
    nombre: datos.nombre,
    categoria: texto(formData, "categoria") || undefined,
    marca: texto(formData, "marca") || undefined,
    modelo: texto(formData, "modelo") || undefined,
    numero_serie: texto(formData, "numero_serie") || undefined,
    ...(datos.tipo === "vehiculo" ? camposVehiculo(formData) : {}),
  };
}

export async function crearActivoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const datos = leerFormulario(formData);
  const errorValidacion = validar(formData, datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/assets/activos", {
      token: await token(),
      metodo: "POST",
      cuerpo: cuerpoAlta(formData, datos),
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el activo.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
