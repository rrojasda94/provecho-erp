import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { OrdenesCliente, type Almacen, type Articulo, type Orden } from "./ordenes-cliente";

export default async function ProduccionPage() {
  const { token } = await obtenerSesion();

  try {
    const [ordenes, articulos, almacenes] = await Promise.all([
      apiFetch<Pagina<Orden>>("/api/v1/production/ordenes", { token }),
      // El artículo a producir y los insumos a consumir salen del mismo
      // catálogo: una subreceta es artículo como cualquier otro.
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
    return (
      <OrdenesCliente
        ordenes={ordenes.items}
        articulos={articulos.items}
        almacenes={almacenes}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver producción."
        : "No se pudieron cargar las órdenes de producción.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
