import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type { ArbolProducto, Articulo, Producto, Receta, UnidadMedida } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { FichaProducto, type ListaPrecio } from "./ficha-cliente";

export default async function ProductoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  try {
    // El árbol trae de una sola vez lo que antes eran dos llamadas —la
    // ficha y los atributos— y es lo mismo que la sección de atributos
    // necesita para dibujarse sin pedir nada aparte.
    const [producto, recetas, unidades, productos, articulos] = await Promise.all([
      apiFetch<ArbolProducto>(`/api/v1/sales/productos/${id}/arbol`, { token }),
      apiFetch<Receta[]>("/api/v1/inventory/recetas", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Producto[]>("/api/v1/sales/productos", { token }),
      // `?tipo=empaque` y no un filtro en el cliente: la lista viene
      // paginada, así que filtrar lo que llegó deja el desplegable vacío en
      // cuanto el catálogo pasa de una página — y un desplegable vacío no
      // dice "faltan", parece que no hay empaques.
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?tipo=empaque", {
        token,
      }),
    ]);
    const listas = await apiFetch<ListaPrecio[]>(
      `/api/v1/sales/listas-precio?marca_id=${producto.marca_id}`,
      { token },
    );
    return (
      <FichaProducto
        inicial={producto}
        recetas={recetas}
        unidades={unidades}
        extrasDisponibles={productos.filter((p) => p.es_extra)}
        // Ya vienen filtrados por tipo desde el servidor; acá solo se cae lo
        // archivado, que es como se retira un empaque sin borrar su historia.
        empaques={articulos.items.filter((a) => !a.archivado)}
        listas={listas}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver este producto."
        : "No se pudo cargar el producto.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
