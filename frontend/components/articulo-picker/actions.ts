"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { COOKIE_TOKEN } from "@/lib/auth";
import type { Opcion } from "@/lib/filtrar-opciones";

type ArticuloBuscado = {
  id: string;
  id_interno: string;
  nombre: string;
  archivado: boolean;
};

/**
 * Typeahead del catálogo de artículos (`/inventory/articulos?q=`).
 *
 * Existe porque este catálogo es el único que **no entra** en una página: son
 * miles contra un techo de 200 filas, así que filtrar en el navegador lo ya
 * recibido deja invisible casi todo y no lo dice. El resto de los desplegables
 * del ERP filtra en el cliente y no necesita nada de esto.
 *
 * Falla en silencio hacia una lista vacía, igual que `buscarPersonasAction`:
 * es un buscador incidental dentro de otro formulario, no una pantalla con su
 * propio estado de error.
 */
export async function buscarArticulosAction(
  consulta: string,
  tipos?: readonly string[],
): Promise<Opcion[]> {
  const store = await cookies();
  const token = store.get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const params = new URLSearchParams({ q: consulta, page_size: "50" });
  for (const tipo of tipos ?? []) params.append("tipo", tipo);

  try {
    const pagina = await apiFetch<Pagina<ArticuloBuscado>>(
      `/api/v1/inventory/articulos?${params}`,
      { token },
    );
    // Lo archivado no se ofrece: no se compra, no se produce y no entra en una
    // receta nueva. El endpoint sí lo devuelve —hay pantallas que lo listan
    // para desarchivarlo—, así que el corte se hace acá.
    return pagina.items
      .filter((a) => !a.archivado)
      .map((a) => ({ valor: a.id, etiqueta: a.nombre, pista: a.id_interno }));
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return [];
  }
}
