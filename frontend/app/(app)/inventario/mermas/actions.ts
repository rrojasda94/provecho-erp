"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import { estadoDeError } from "@/lib/errores";

const RUTA = "/inventario/mermas";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

/**
 * Registra una merma (RN-INV-012, ADR-028).
 *
 * No saca el stock del almacén: lo saca de la venta. Es una reserva de tipo
 * `merma`, y qué se hace con lo apartado —tirarlo o devolverlo al estante—
 * lo firma otro usuario al resolverla. Esa segregación es la razón de que
 * sean dos pasos y no un formulario con un desplegable de destino.
 */
export async function registrarMermaAction(
  _previo: EstadoFormulario,
  formData: FormData,
): Promise<EstadoFormulario> {
  const cantidad = texto(formData, "cantidad");
  if (!texto(formData, "almacen_id")) return { error: "Elige el almacén.", ok: false };
  if (!texto(formData, "sku_id")) return { error: "Elige qué se aparta.", ok: false };
  if (!cantidad || Number(cantidad) <= 0) {
    return { error: "La cantidad debe ser mayor que cero.", ok: false };
  }

  try {
    await apiFetch("/api/v1/inventory/mermas", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        almacen_id: texto(formData, "almacen_id"),
        sku_id: texto(formData, "sku_id"),
        cantidad,
        motivo: texto(formData, "motivo"),
        lote_id: texto(formData, "lote_id") || null,
      },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo registrar la merma.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/**
 * Resuelve una merma apartada: `desecho` la saca del stock y publica
 * `inventory.merma_registrada` —que `accounting` asienta como pérdida—;
 * `reintegro` la devuelve a disponible.
 *
 * Exige `inventory.aprobar_ajuste`, que es un permiso distinto del de
 * registrarla: quien declara que algo no sirve no firma su baja.
 */
export async function resolverMermaAction(
  reservaId: string,
  destino: "desecho" | "reintegro",
): Promise<EstadoFormulario> {
  try {
    await apiFetch(`/api/v1/inventory/mermas/${reservaId}/resolver`, {
      token: await token(),
      metodo: "POST",
      cuerpo: { destino },
    });
  } catch (e) {
    return estadoDeError(e, "No se pudo resolver la merma.");
  }
  revalidatePath(RUTA);
  return { error: "", ok: true };
}
