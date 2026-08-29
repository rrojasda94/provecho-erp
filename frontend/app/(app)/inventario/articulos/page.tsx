import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  ArticulosCliente,
  type Articulo,
  type Categoria,
  type UnidadMedida,
} from "./articulos-cliente";

export default async function ArticulosPage() {
  const { token } = await obtenerSesion();

  try {
    // En paralelo: la tabla necesita el listado, el diálogo de alta
    // necesita las dos listas de referencia — ninguna depende de la otra.
    const [articulos, categorias, unidadesMedida] = await Promise.all([
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", { token }),
      apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
    ]);
    return (
      <ArticulosCliente
        articulos={articulos.items}
        categorias={categorias}
        unidadesMedida={unidadesMedida}
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
