"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoOrden = { error: string; ok: boolean };

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ApiError ? e.message : porDefecto;
}

export async function crearOrdenAction(
  _previo: EstadoOrden,
  formData: FormData,
): Promise<EstadoOrden> {
  const articuloId = String(formData.get("articulo_id") ?? "");
  const almacenId = String(formData.get("almacen_id") ?? "");
  const cantidad = String(formData.get("cantidad_planeada") ?? "");
  if (!articuloId || !almacenId) return { error: "Elegir artículo y almacén.", ok: false };
  if (Number(cantidad) <= 0) return { error: "La cantidad planeada debe ser > 0.", ok: false };

  try {
    await apiFetch("/api/v1/production/ordenes", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        articulo_id: articuloId,
        almacen_id: almacenId,
        cantidad_planeada: cantidad,
        // Client-generada, como en el PDV y en las órdenes de compra: si el
        // navegador reintenta el POST, no salen dos órdenes.
        idempotency_key: `op-${crypto.randomUUID()}`,
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la orden."), ok: false };
  }
  revalidatePath("/produccion");
  return { error: "", ok: true };
}

type ConsumoItem = { articulo_id: string; cantidad: number; costo_unitario: number };

function leerConsumo(formData: FormData): ConsumoItem[] {
  const articulos = formData.getAll("consumo_articulo_id").map(String);
  const cantidades = formData.getAll("consumo_cantidad").map(String);
  const costos = formData.getAll("consumo_costo").map(String);
  return articulos
    .map((articulo, i) => ({
      articulo_id: articulo,
      cantidad: Number(cantidades[i] ?? 0),
      costo_unitario: Number(costos[i] ?? 0),
    }))
    .filter((it) => it.articulo_id && it.cantidad > 0);
}

export async function registrarConsumoAction(
  _previo: EstadoOrden,
  formData: FormData,
): Promise<EstadoOrden> {
  const ordenId = String(formData.get("orden_id") ?? "");
  const items = leerConsumo(formData);
  if (!ordenId) return { error: "Falta la orden.", ok: false };
  if (items.length === 0) return { error: "Registrar al menos un insumo consumido.", ok: false };

  try {
    await apiFetch(`/api/v1/production/ordenes/${ordenId}/consumo`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { items },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo registrar el consumo."), ok: false };
  }
  revalidatePath("/produccion");
  return { error: "", ok: true };
}

/** Solo los campos con valor viajan: el backend distingue "no informado"
 * de "cero", y mandar cadenas vacías lo rompería. */
function opcional(formData: FormData, campo: string): string | undefined {
  return String(formData.get(campo) ?? "").trim() || undefined;
}

export async function completarOrdenAction(
  _previo: EstadoOrden,
  formData: FormData,
): Promise<EstadoOrden> {
  const ordenId = String(formData.get("orden_id") ?? "");
  const resultado = String(formData.get("resultado") ?? "");
  if (!ordenId || !resultado) return { error: "Falta el resultado del control.", ok: false };

  try {
    await apiFetch(`/api/v1/production/ordenes/${ordenId}/completar`, {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        resultado,
        cantidad_producida: opcional(formData, "cantidad_producida"),
        horas_hombre: opcional(formData, "horas_hombre"),
        merma_cantidad: opcional(formData, "merma_cantidad"),
        merma_motivo: opcional(formData, "merma_motivo"),
        evidencia_destruccion_url: opcional(formData, "evidencia_destruccion_url"),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo completar la orden."), ok: false };
  }
  revalidatePath("/produccion");
  return { error: "", ok: true };
}
