"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";

export type EstadoArticulo = { error: string; ok: boolean };

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
    idInterno: String(formData.get("id_interno") ?? "").trim(),
    nombre: String(formData.get("nombre") ?? "").trim(),
    tipo: String(formData.get("tipo") ?? ""),
    unidadMedidaId: String(formData.get("unidad_medida_id") ?? ""),
    categoriaId: String(formData.get("categoria_id") ?? ""),
    costoPromedio: String(formData.get("costo_promedio") ?? "0").trim(),
  };
}

function validar(datos: DatosArticulo): string | null {
  if (!datos.idInterno || !datos.nombre) return "Código y nombre son obligatorios.";
  if (datos.idInterno.length > 4) return "El código interno son máximo 4 caracteres.";
  if (!datos.unidadMedidaId) return "La unidad de medida es obligatoria.";
  return null;
}

export async function crearArticuloAction(
  _previo: EstadoArticulo,
  formData: FormData,
): Promise<EstadoArticulo> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const datos = leerFormulario(formData);
  const errorValidacion = validar(datos);
  if (errorValidacion) return { error: errorValidacion, ok: false };

  try {
    await apiFetch("/api/v1/inventory/articulos", {
      token,
      metodo: "POST",
      cuerpo: {
        id_interno: datos.idInterno,
        nombre: datos.nombre,
        tipo: datos.tipo,
        unidad_medida_id: datos.unidadMedidaId,
        categoria_id: datos.categoriaId || undefined,
        costo_promedio: datos.costoPromedio || "0",
      },
    });
  } catch (e) {
    const mensaje = e instanceof ApiError ? e.message : "No se pudo crear el artículo.";
    return { error: mensaje, ok: false };
  }

  revalidatePath("/inventario/articulos");
  return { error: "", ok: true };
}
