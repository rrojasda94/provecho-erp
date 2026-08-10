"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { EstadoFormulario } from "@/components/formulario/dialogo-formulario";
import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoArticulo = EstadoFormulario;

const RUTA = "/inventario/articulos";

async function token(): Promise<string> {
  const store = await cookies();
  const valor = store.get(COOKIE_TOKEN)?.value;
  if (!valor) redirect("/login");
  return valor;
}

function texto(formData: FormData, campo: string): string {
  return String(formData.get(campo) ?? "").trim();
}

type DatosArticulo = {
  idInterno: string;
  nombre: string;
  tipo: string;
  unidadMedidaId: string;
  categoriaId: string;
  costoPromedio: string;
};

function leerFormulario(formData: FormData): DatosArticulo {
  return {
    idInterno: texto(formData, "id_interno"),
    nombre: texto(formData, "nombre"),
    tipo: String(formData.get("tipo") ?? ""),
    unidadMedidaId: String(formData.get("unidad_medida_id") ?? ""),
    categoriaId: String(formData.get("categoria_id") ?? ""),
    costoPromedio: texto(formData, "costo_promedio") || "0",
  };
}

function validarComunes(datos: DatosArticulo): string | null {
  if (!datos.idInterno || !datos.nombre) return "Código y nombre son obligatorios.";
  if (datos.idInterno.length > 4) return "El código interno son máximo 4 caracteres.";
  return null;
}

export async function crearArticuloAction(
  _previo: EstadoArticulo,
  formData: FormData,
): Promise<EstadoArticulo> {
  const datos = leerFormulario(formData);
  const errorValidacion =
    validarComunes(datos) ??
    (datos.unidadMedidaId ? null : "La unidad de medida es obligatoria.");
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/inventory/articulos", {
      token: await token(),
      metodo: "POST",
      cuerpo: {
        id_interno: datos.idInterno,
        nombre: datos.nombre,
        tipo: datos.tipo,
        unidad_medida_id: datos.unidadMedidaId,
        categoria_id: datos.categoriaId || undefined,
        costo_promedio: datos.costoPromedio,
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el artículo.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}

/** Corrección de un artículo existente.
 *
 * `unidad_medida_id` no viaja: la API tampoco lo acepta. El stock y las
 * recetas ya cargadas están expresados en la unidad actual. */
export async function editarArticuloAction(
  _previo: EstadoArticulo,
  formData: FormData,
): Promise<EstadoArticulo> {
  const id = texto(formData, "id");
  if (!id) return { error: "Falta el artículo a editar.", ok: false };

  const datos = leerFormulario(formData);
  const errorValidacion = validarComunes(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  const dias = texto(formData, "dias_alerta_vencimiento");

  try {
    await apiFetch(`/api/v1/inventory/articulos/${id}`, {
      token: await token(),
      metodo: "PATCH",
      cuerpo: {
        id_interno: datos.idInterno,
        nombre: datos.nombre,
        tipo: datos.tipo,
        // Vaciar la categoría no se puede desde el PATCH (`null` significa
        // "no tocar", ver ArticuloUpdate) — se cambia por otra, no se quita.
        categoria_id: datos.categoriaId || undefined,
        costo_promedio: datos.costoPromedio,
        dias_alerta_vencimiento: dias === "" ? undefined : Number(dias),
        controla_lote: formData.get("controla_lote") === "on",
        archivado: formData.get("archivado") === "on",
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo guardar el artículo.";
    return { error: mensaje, ok: false };
  }

  revalidatePath(RUTA);
  return { error: "", ok: true };
}
