"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoTrabajador = EstadoFormulario;

const RUTA = "/rrhh/trabajadores";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

export async function crearTrabajadorAction(
  _previo: EstadoTrabajador,
  formData: FormData,
): Promise<EstadoTrabajador> {
  const personaId = texto(formData, "persona_id");
  const cargo = texto(formData, "cargo");
  const area = texto(formData, "area");
  const tipoVinculo = String(formData.get("tipo_vinculo") ?? "planilla");
  const fechaIngreso = texto(formData, "fecha_ingreso");

  if (!personaId) return { error: "Elegir la persona.", ok: false };
  if (!cargo || !area) return { error: "Cargo y área son obligatorios.", ok: false };
  if (!fechaIngreso) return { error: "La fecha de ingreso es obligatoria.", ok: false };

  try {
    await apiFetch("/api/v1/rrhh/trabajadores", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        persona_id: personaId,
        cargo,
        area,
        tipo_vinculo: tipoVinculo,
        fecha_ingreso: fechaIngreso,
        // Locación de servicios nunca marca asistencia (RN-PER-002) — el
        // backend lo exige, así que no se manda una casilla que confundiría.
        registra_asistencia: tipoVinculo !== "locacion_servicios",
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el trabajador.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Corrección de un trabajador existente.
 *
 * No incluye el cese: cesar tiene su propio endpoint porque además del
 * estado fija la fecha y publica el evento del que cuelga la liquidación. */
export async function editarTrabajadorAction(
  _previo: EstadoTrabajador,
  formData: FormData,
): Promise<EstadoTrabajador> {
  const id = texto(formData, "id");
  if (!id) return { error: "Falta el trabajador a editar.", ok: false };

  const cargo = texto(formData, "cargo");
  const area = texto(formData, "area");
  if (!cargo || !area) return { error: "Cargo y área son obligatorios.", ok: false };

  const remuneracion = texto(formData, "remuneracion_base");

  try {
    await apiFetch(`/api/v1/rrhh/trabajadores/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        cargo,
        area,
        remuneracion_base: remuneracion === "" ? undefined : remuneracion,
        estado: String(formData.get("estado") ?? "activo"),
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo guardar el trabajador.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Cese: cambia el estado *y* fija la fecha, que es lo que la liquidación
 * necesita. Separado de la edición a propósito — es una salida, no una
 * corrección de datos. */
export async function cesarTrabajadorAction(
  _previo: EstadoTrabajador,
  formData: FormData,
): Promise<EstadoTrabajador> {
  const id = texto(formData, "id");
  const fechaCese = texto(formData, "fecha_cese");
  if (!id) return { error: "Falta el trabajador.", ok: false };
  if (!fechaCese) return { error: "La fecha de cese es obligatoria.", ok: false };

  try {
    await apiFetch(`/api/v1/rrhh/trabajadores/${id}/cesar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { fecha_cese: fechaCese },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo registrar el cese.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
