import { ApiError, apiFetch } from "@/lib/api";
import type { Producto, ProductoDetalle, Receta, UnidadMedida } from "@/lib/catalogo";
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
    // Todo lo que la ficha necesita para elegir sin volver al servidor por
    // cada desplegable. Las recetas se **eligen** acá, no se editan: eso
    // vive en Catálogo → Recetas y duplicarlo confundía más que ayudar.
    const [producto, recetas, unidades, productos] = await Promise.all([
      apiFetch<ProductoDetalle>(`/api/v1/sales/productos/${id}`, { token }),
      apiFetch<Receta[]>("/api/v1/inventory/recetas", { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Producto[]>("/api/v1/sales/productos", { token }),
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
