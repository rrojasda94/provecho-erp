"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoCatalogo = EstadoFormulario;

const RUTA_CATEGORIAS = "/inventario/categorias";
const RUTA_UNIDADES = "/inventario/unidades-medida";

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

// --- Categorías de artículo -------------------------------------------------

export async function crearCategoriaAction(
  _previo: EstadoCatalogo,
  formData: FormData,
): Promise<EstadoCatalogo> {
  const nombre = texto(formData, "nombre");
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  try {
    await apiFetch("/api/v1/inventory/categorias", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        nombre,
        frecuencia_conteo: texto(formData, "frecuencia_conteo") || undefined,
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la categoría."), ok: false };
  }
  revalidatePath(RUTA_CATEGORIAS);
  return { error: "", ok: true };
}

/** La frecuencia es el único campo del ERP que se puede *vaciar* desde un
 * PATCH, y necesita un centinela para eso: `frecuencia_conteo: null` sería
 * indistinguible de "no la mandaron". Sin `quitar_frecuencia`, sacar una
 * categoría del conteo cíclico era imposible. */
export async function editarCategoriaAction(
  _previo: EstadoCatalogo,
  formData: FormData,
): Promise<EstadoCatalogo> {
  const id = texto(formData, "id");
  const nombre = texto(formData, "nombre");
  if (!id) return { error: "Falta la categoría a editar.", ok: false };
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  const frecuencia = texto(formData, "frecuencia_conteo");

  try {
    await apiFetch(`/api/v1/inventory/categorias/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        nombre,
        frecuencia_conteo: frecuencia || undefined,
        quitar_frecuencia: frecuencia === "",
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar la categoría."), ok: false };
  }
  revalidatePath(RUTA_CATEGORIAS);
  return { error: "", ok: true };
}

// --- Unidades de medida -----------------------------------------------------

export async function crearCategoriaUdmAction(
  _previo: EstadoCatalogo,
  formData: FormData,
): Promise<EstadoCatalogo> {
  const nombre = texto(formData, "nombre");
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  try {
    await apiFetch("/api/v1/inventory/categorias-udm", {
      token: await token(),
      metodo: "POST",
      cuerpo: { nombre },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la magnitud."), ok: false };
  }
  revalidatePath(RUTA_UNIDADES);
  return { error: "", ok: true };
}

export async function crearUnidadMedidaAction(
  _previo: EstadoCatalogo,
  formData: FormData,
): Promise<EstadoCatalogo> {
  const nombre = texto(formData, "nombre");
  const categoriaUdmId = texto(formData, "categoria_udm_id");
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };
  if (!categoriaUdmId) return { error: "Elegir la magnitud.", ok: false };

  try {
    await apiFetch("/api/v1/inventory/unidades-medida", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        categoria_udm_id: categoriaUdmId,
        nombre,
        ratio: texto(formData, "ratio") || "1",
        decimales: Number(formData.get("decimales") ?? 3),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo crear la unidad."), ok: false };
  }
  revalidatePath(RUTA_UNIDADES);
  return { error: "", ok: true };
}

/** La magnitud (`categoria_udm_id`) no se edita ni la API la acepta:
 * cambiarla haría que el ratio pase a compararse contra otra unidad base,
 * o sea que toda conversión ya hecha con esta unidad quede mal. */
export async function editarUnidadMedidaAction(
  _previo: EstadoCatalogo,
  formData: FormData,
): Promise<EstadoCatalogo> {
  const id = texto(formData, "id");
  const nombre = texto(formData, "nombre");
  if (!id) return { error: "Falta la unidad a editar.", ok: false };
  if (!nombre) return { error: "El nombre es obligatorio.", ok: false };

  try {
    await apiFetch(`/api/v1/inventory/unidades-medida/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        nombre,
        ratio: texto(formData, "ratio") || undefined,
        decimales: Number(formData.get("decimales") ?? 3),
      },
    });
  } catch (e) {
    return { error: mensajeDe(e, "No se pudo guardar la unidad."), ok: false };
  }
  revalidatePath(RUTA_UNIDADES);
  return { error: "", ok: true };
}
