"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoTrabajador = { error: string; ok: boolean };

type DatosTrabajador = {
  personaId: string;
  cargo: string;
  area: string;
  tipoVinculo: string;
  fechaIngreso: string;
};

function leerFormulario(formData: FormData): DatosTrabajador {
  return {
    personaId: String(formData.get("persona_id") ?? ""),
    cargo: String(formData.get("cargo") ?? "").trim(),
    area: String(formData.get("area") ?? "").trim(),
    tipoVinculo: String(formData.get("tipo_vinculo") ?? "planilla"),
    fechaIngreso: String(formData.get("fecha_ingreso") ?? ""),
  };
}

function validar(datos: DatosTrabajador): string | null {
  if (!datos.personaId) return "Elegir la persona.";
  if (!datos.cargo || !datos.area) return "Cargo y área son obligatorios.";
  if (!datos.fechaIngreso) return "La fecha de ingreso es obligatoria.";
  return null;
}

export async function crearTrabajadorAction(
  _previo: EstadoTrabajador,
  formData: FormData,
): Promise<EstadoTrabajador> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const datos = leerFormulario(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/rrhh/trabajadores", {
      token,
      metodo: "POST",
      cuerpo: {
        persona_id: datos.personaId,
        cargo: datos.cargo,
        area: datos.area,
        tipo_vinculo: datos.tipoVinculo,
        fecha_ingreso: datos.fechaIngreso,
        // Locación de servicios nunca marca asistencia (RN-PER-002) — el
        // backend lo exige, así que no se manda una casilla que confundiría.
        registra_asistencia: datos.tipoVinculo !== "locacion_servicios",
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el trabajador.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/rrhh/trabajadores");
  return { error: "", ok: true };
}
