"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoChecklist = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

type EquipoFrio = {
  equipo: string;
  temperatura_c: string;
  rango_min: string;
  rango_max: string;
};

/** Mismo patrón `getAll` que `leerTrabajadores` en `produccion/actions.ts`:
 * cada línea del picker de equipos son campos repetidos con el mismo
 * `name`. `dentro_rango` no viaja: lo calcula el servidor. */
function leerEquiposFrio(formData: FormData): EquipoFrio[] {
  const equipos = formData.getAll("equipo_nombre").map(String);
  const temperaturas = formData.getAll("equipo_temperatura").map(String);
  const rangosMin = formData.getAll("equipo_rango_min").map(String);
  const rangosMax = formData.getAll("equipo_rango_max").map(String);
  return equipos
    .map((equipo, i) => ({
      equipo,
      temperatura_c: temperaturas[i] ?? "",
      rango_min: rangosMin[i] ?? "",
      rango_max: rangosMax[i] ?? "",
    }))
    .filter((e) => e.equipo && e.temperatura_c && e.rango_min && e.rango_max);
}

export async function crearChecklistAction(
  _previo: EstadoChecklist,
  formData: FormData,
): Promise<EstadoChecklist> {
  const almacenId = String(formData.get("almacen_id") ?? "");
  const fecha = String(formData.get("fecha") ?? "");
  const turno = String(formData.get("turno") ?? "");
  if (!almacenId || !fecha || !turno) {
    return { error: "Completar almacén, fecha y turno.", ok: false };
  }

  try {
    await apiFetch("/api/v1/production/checklists", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: almacenId,
        fecha,
        turno,
        bioseguridad_ok: formData.get("bioseguridad_ok") === "on",
        superficies_ok: formData.get("superficies_ok") === "on",
        limpieza_intermedia_ok: formData.get("limpieza_intermedia_ok") === "on",
        plaga_indicio: formData.get("plaga_indicio") === "on",
        equipos_frio: leerEquiposFrio(formData),
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar el checklist.");
  }
  revalidatePath("/produccion/inocuidad");
  return { error: "", ok: true };
}
