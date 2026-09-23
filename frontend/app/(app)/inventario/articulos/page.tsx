import { ApiError, apiFetch, leerPagina, type Pagina, type ParamsPagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  ArticulosCliente,
  type Articulo,
  type Categoria,
  type UnidadMedida,
} from "./articulos-cliente";

/**
 * Catálogo de artículos, paginado y buscado en el servidor. Pedía una sola
 * página de 200 y filtraba en el navegador: el artículo 201 no aparecía ni
 * buscándolo por nombre.
 */
export default async function ArticulosPage({
  searchParams,
}: {
  searchParams: Promise<ParamsPagina>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { query, pagina, tamano, q } = leerPagina(await searchParams);

  try {
    // En paralelo: la tabla necesita el listado, el diálogo de alta
    // necesita las dos listas de referencia — ninguna depende de la otra.
    const [articulos, categorias, unidadesMedida] = await Promise.all([
      apiFetch<Pagina<Articulo>>(`/api/v1/inventory/articulos?${query}`, { token }),
      apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
    ]);
    return (
      <ArticulosCliente
        articulos={articulos.items}
        pagina={{ total: articulos.total, page: pagina, pageSize: tamano, q }}
        categorias={categorias}
        unidadesMedida={unidadesMedida}
        permisos={usuario.permisos}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver artículos."
        : "No se pudo cargar el catálogo de artículos.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
