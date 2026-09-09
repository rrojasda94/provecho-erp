"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

export type EstadoPlan = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

export async function crearPlanAction(
  _previo: EstadoPlan,
  formData: FormData,
): Promise<EstadoPlan> {
  const almacenId = String(formData.get("almacen_id") ?? "");
  const fecha = String(formData.get("fecha") ?? "");
  const turno = String(formData.get("turno") ?? "");
  const lineaProduccion = String(formData.get("linea_produccion") ?? "");
  if (!almacenId || !fecha || !turno || !lineaProduccion) {
    return { error: "Completar almacén, fecha, turno y línea.", ok: false };
  }

  try {
    await apiFetch("/api/v1/production/planes", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: almacenId, fecha, turno, linea_produccion: lineaProduccion,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo crear el plan.");
  }
  revalidatePath("/produccion/plan");
  return { error: "", ok: true };
}

export async function agregarOrdenAPlanAction(
  _previo: EstadoPlan,
  formData: FormData,
): Promise<EstadoPlan> {
  const planId = String(formData.get("plan_id") ?? "");
  const articuloId = String(formData.get("articulo_id") ?? "");
  const cantidad = String(formData.get("cantidad_planeada") ?? "");
  if (!planId || !articuloId) return { error: "Elegir qué se produce.", ok: false };
  if (Number(cantidad) <= 0) return { error: "La cantidad planeada debe ser > 0.", ok: false };

  try {
    await apiFetch(`/api/v1/production/planes/${planId}/ordenes`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        articulo_id: articuloId,
        cantidad_planeada: cantidad,
        // Client-generada, como en el resto del módulo: un reintento de red
        // no duplica la orden.
        idempotency_key: `plan-${crypto.randomUUID()}`,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo agregar la orden al plan.");
  }
  revalidatePath("/produccion/plan");
  return { error: "", ok: true };
}

export async function iniciarPlanAction(
  _previo: EstadoPlan,
  formData: FormData,
): Promise<EstadoPlan> {
  const planId = String(formData.get("plan_id") ?? "");
  if (!planId) return { error: "Falta el plan.", ok: false };
  try {
    await apiFetch(`/api/v1/production/planes/${planId}/iniciar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo iniciar el plan.");
  }
  revalidatePath("/produccion/plan");
  return { error: "", ok: true };
}

export async function cerrarPlanAction(
  _previo: EstadoPlan,
  formData: FormData,
): Promise<EstadoPlan> {
  const planId = String(formData.get("plan_id") ?? "");
  if (!planId) return { error: "Falta el plan.", ok: false };
  try {
    await apiFetch(`/api/v1/production/planes/${planId}/cerrar`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo cerrar el plan.");
  }
  revalidatePath("/produccion/plan");
  return { error: "", ok: true };
}
