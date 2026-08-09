import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import type {
  Articulo,
  Producto,
  ProductoDetalle,
  Receta,
  UnidadMedida,
} from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { LienzoNodos } from "./nodos-cliente";

export default async function NodosPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  try {
    const [producto, recetas, unidades, productos, articulos] = await Promise.all([
      apiFetch<ProductoDetalle>(`/api/v1/sales/productos/${id}`, { token }),
      apiFetch<Receta[]>("/api/v1/inventory/recetas", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Producto[]>("/api/v1/sales/productos", { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos", { token }),
    ]);
    // Cada tamaño trae SUS grupos: "Peperoni" en Personal y en Familiar son
    // dos opciones distintas con dos recetas distintas (otros gramos), no la
    // misma opción vista dos veces. Por eso la ficha de la variante, y no
    // solo la del padre.
    const variantes = await Promise.all(
      producto.variantes.map((v) =>
        apiFetch<ProductoDetalle>(`/api/v1/sales/productos/${v.id}`, { token }),
      ),
    );

    return (
      <LienzoNodos
        inicial={producto}
        variantesIniciales={variantes}
        recetas={recetas}
        unidades={unidades}
        extrasDisponibles={productos.filter((p) => p.es_extra)}
        empaques={articulos.items.filter((a) => !a.archivado)}
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
