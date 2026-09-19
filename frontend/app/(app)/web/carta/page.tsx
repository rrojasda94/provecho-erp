import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { CartaCliente, type Foto, type Producto } from "./carta-cliente";

export default async function WebCartaPage() {
  const { token } = await obtenerSesion();

  try {
    const marcas = await apiFetch<{ id: string; nombre: string }[]>("/api/v1/marcas", {
      token,
    });
    const marca = marcas[0];
    if (!marca) {
      return <p className="text-secondary">No hay ninguna marca cargada todavía.</p>;
    }

    const todos = await apiFetch<Producto[]>(
      `/api/v1/sales/productos?marca_id=${marca.id}`,
      { token },
    );
    // Lo que sale en el sitio público es lo mismo que sale en la carta del
    // PDV: productos "de verdad", no el padre agrupador de variantes ni un
    // extra suelto (`sales.application.precios.carta` filtra igual).
    const productos = todos.filter((p) => p.activo && !p.es_extra && !p.producto_padre_id);

    // Una sola llamada para todas las fotos: una por producto agotaba el
    // pool de conexiones de la API (QueuePool limit).
    const ids = productos.map((p) => `ids=${p.id}`).join("&");
    const fotosPorProducto = productos.length
      ? await apiFetch<Record<string, Foto[]>>(
          `/api/v1/storefront/fotos?entidad=producto&${ids}`,
          { token },
        )
      : {};

    return <CartaCliente productos={productos} fotosPorProducto={fotosPorProducto} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver la carta del sitio web."
        : "No se pudo cargar la carta del sitio web.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
