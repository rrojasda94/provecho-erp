"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoMarketing = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

function leerBrief(formData: FormData) {
  return {
    objetivo: String(formData.get("objetivo") ?? "").trim() || undefined,
    publico_objetivo: String(formData.get("publico_objetivo") ?? "").trim() || undefined,
    presupuesto: String(formData.get("presupuesto") ?? "").trim() || undefined,
    kpi: String(formData.get("kpi") ?? "").trim() || undefined,
  };
}

export async function crearCampanaAction(
  _previo: EstadoMarketing,
  formData: FormData,
): Promise<EstadoMarketing> {
  const marcaId = String(formData.get("marca_id") ?? "");
  const nombre = String(formData.get("nombre") ?? "").trim();
  if (!marcaId || nombre.length < 3) {
    return { error: "Marca y nombre (3 caracteres o más) son obligatorios.", ok: false };
  }

  try {
    await apiFetch("/api/v1/marketing/campanas", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        marca_id: marcaId,
        nombre,
        tipo: String(formData.get("tipo") ?? "impulso_venta"),
        canal: String(formData.get("canal") ?? "").trim(),
        idempotency_key: `mkt-${crypto.randomUUID()}`,
        ...leerBrief(formData),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la campaña."), ok: false };
  }
  revalidatePath("/marketing");
  return { error: "", ok: true };
}

export async function completarBriefAction(
  _previo: EstadoMarketing,
  formData: FormData,
): Promise<EstadoMarketing> {
  const campanaId = String(formData.get("campana_id") ?? "");
  if (!campanaId) return { error: "Falta la campaña.", ok: false };

  try {
    await apiFetch(`/api/v1/marketing/campanas/${campanaId}/brief`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: leerBrief(formData),
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar el brief."), ok: false };
  }
  revalidatePath("/marketing");
  return { error: "", ok: true };
}

/** Aprobar / lanzar / cerrar: el ciclo de RN-MKT-003. Quien redacta el
 * brief no lo aprueba — el permiso `marketing.campana_aprobar` vive en
 * `supervisor`, así que un 403 acá es la regla funcionando, no un bug. */
export async function avanzarCampanaAction(
  campanaId: string,
  paso: "aprobacion" | "lanzamiento" | "cierre",
): Promise<EstadoMarketing> {
  try {
    await apiFetch(`/api/v1/marketing/campanas/${campanaId}/${paso}`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo avanzar la campaña."), ok: false };
  }
  revalidatePath("/marketing");
  return { error: "", ok: true };
}

function leerPieza(formData: FormData) {
  return {
    marca_id: String(formData.get("marca_id") ?? ""),
    titulo: String(formData.get("titulo") ?? "").trim(),
    canal: String(formData.get("canal") ?? "").trim(),
    fecha_publicacion: String(formData.get("fecha_publicacion") ?? ""),
    campana_id: String(formData.get("campana_id") ?? "") || undefined,
    pertinente_marca: formData.get("pertinente_marca") === "on",
    uso_marca_validado: formData.get("uso_marca_validado") === "on",
  };
}

export async function crearPiezaAction(
  _previo: EstadoMarketing,
  formData: FormData,
): Promise<EstadoMarketing> {
  const pieza = leerPieza(formData);
  if (
    !pieza.marca_id ||
    pieza.titulo.length < 3 ||
    !pieza.canal ||
    !pieza.fecha_publicacion
  ) {
    return { error: "Marca, título, canal y fecha son obligatorios.", ok: false };
  }

  try {
    await apiFetch("/api/v1/marketing/piezas", {
      token: await token(),
      metodo: "POST",
      cuerpo: pieza,
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo planificar la pieza."), ok: false };
  }
  revalidatePath("/marketing/contenido");
  return { error: "", ok: true };
}

export async function validarPiezaAction(
  piezaId: string,
  campo: "pertinente_marca" | "uso_marca_validado",
  valor: boolean,
): Promise<EstadoMarketing> {
  try {
    await apiFetch(`/api/v1/marketing/piezas/${piezaId}/validacion`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: { [campo]: valor },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo validar la pieza."), ok: false };
  }
  revalidatePath("/marketing/contenido");
  return { error: "", ok: true };
}

export async function publicarPiezaAction(piezaId: string): Promise<EstadoMarketing> {
  try {
    await apiFetch(`/api/v1/marketing/piezas/${piezaId}/publicacion`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {},
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo publicar la pieza."), ok: false };
  }
  revalidatePath("/marketing/contenido");
  return { error: "", ok: true };
}

export async function descartarPiezaAction(piezaId: string): Promise<EstadoMarketing> {
  try {
    await apiFetch(`/api/v1/marketing/piezas/${piezaId}/descarte`, {
      token: await token(),
      metodo: "POST",
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo descartar la pieza."), ok: false };
  }
  revalidatePath("/marketing/contenido");
  return { error: "", ok: true };
}
