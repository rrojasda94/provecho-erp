"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

const RUTA = "/inventario/conteos";

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

/**
 * Abre el conteo y lleva a la grilla.
 *
 * Sin categoría es un conteo **general**: cuenta todo el almacén y pone al
 * día el calendario de todas sus categorías (RN-INV-007).
 */
export async function abrirConteoAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  if (!texto(formData, "almacen_id")) return { error: "Elige el almacén.", ok: false };
  let id: string;
  try {
    const conteo = await apiFetch<{ id: string }>("/api/v1/inventory/conteos", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: texto(formData, "almacen_id"),
        categoria_id: texto(formData, "categoria_id") || null,
        tipo: texto(formData, "tipo") || "rutina",
        observacion: texto(formData, "observacion") || null,
      },
    });
    id = conteo.id;
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo abrir el conteo."), ok: false };
  }
  revalidatePath(RUTA);
  redirect(`${RUTA}/${id}`);
}

/**
 * Anota lo contado. Va todo junto y no ítem por ítem: quien cuenta recorre el
 * estante entero y recién después se acerca a la pantalla, así que guardar en
 * cada tecla sería una escritura por dígito y ninguna por decisión.
 */
export async function registrarCantidadesAction(
  conteoId: string,
  cantidades: { sku_id: string; cantidad: string }[],
): Promise<EstadoFormulario> {
  if (cantidades.length === 0) {
    return { error: "Todavía no anotaste ninguna cantidad.", ok: false };
  }
  try {
    await apiFetch(`/api/v1/inventory/conteos/${conteoId}/cantidades`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { items: cantidades },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar lo contado."), ok: false };
  }
  revalidatePath(`${RUTA}/${conteoId}`);
  return { error: "", ok: true };
}

/** Cerrar no mueve stock: solicita un ajuste por diferencia, y ese ajuste lo
 * aprueba alguien distinto del que contó (RN-INV-006). */
export async function cerrarConteoAction(
  conteoId: string,
): Promise<EstadoFormulario & { ajustes: number }> {
  try {
    const r = await apiFetch<{ ajustes: unknown[] }>(
      `/api/v1/inventory/conteos/${conteoId}/cerrar`,
      { token: await token(), metodo: "POST" },
    );
    revalidatePath(`${RUTA}/${conteoId}`);
    return { error: "", ok: true, ajustes: r.ajustes.length };
  } catch (e) {
    return {
      error: mensajeDe(e, "No se pudo cerrar el conteo."),
      ok: false,
      ajustes: 0,
    };
  }
}

/** Anular es la forma de hacer desaparecer un conteo incómodo, así que el
 * motivo es obligatorio y queda escrito en el propio conteo. */
export async function anularConteoAction(
  conteoId: string,
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const motivo = texto(formData, "motivo");
  if (motivo.length < 3) {
    return { error: "Escribe por qué se anula.", ok: false };
  }
  try {
    await apiFetch(`/api/v1/inventory/conteos/${conteoId}/anular`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { motivo },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo anular el conteo."), ok: false };
  }
  revalidatePath(`${RUTA}/${conteoId}`);
  return { error: "", ok: true };
}
