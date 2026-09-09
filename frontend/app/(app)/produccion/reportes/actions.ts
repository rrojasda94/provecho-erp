"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoReporte = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export async function generarReporteJornadaAction(
  _previo: EstadoReporte,
  formData: FormData,
): Promise<EstadoReporte> {
  const almacenId = String(formData.get("almacen_id") ?? "");
  const fecha = String(formData.get("fecha") ?? "").trim();
  if (!almacenId) return { error: "Elegir un almacén.", ok: false };

  try {
    await apiFetch("/api/v1/production/reportes-jornada/generar", {
      token: await token(),
      metodo: "POST",
      cuerpo: fecha ? { almacen_id: almacenId, fecha } : { almacen_id: almacenId },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo generar el reporte.");
  }
  revalidatePath("/produccion/reportes");
  return { error: "", ok: true };
}

export async function visarReporteJornadaAction(
  _previo: EstadoReporte,
  formData: FormData,
): Promise<EstadoReporte> {
  const reporteId = String(formData.get("reporte_id") ?? "");
  const observaciones = String(formData.get("observaciones") ?? "").trim();
  if (!reporteId) return { error: "Falta el reporte.", ok: false };

  try {
    await apiFetch(`/api/v1/production/reportes-jornada/${reporteId}/visar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: observaciones ? { observaciones } : {},
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo visar el reporte.");
  }
  revalidatePath("/produccion/reportes");
  return { error: "", ok: true };
}
