import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ContenidoCliente, type Contenido } from "./contenido-cliente";

type Marca = { id: string; nombre: string; tipo: string };
type ContenidoFila = { clave: string; valor: Record<string, unknown> };

export default async function WebPage() {
  const { token } = await obtenerSesion();

  try {
    const marcas = await apiFetch<Marca[]>("/api/v1/marcas", { token });
    // El grupo opera una sola marca con sitio propio hoy (Charlie's
    // Pizzas); cuando haya más de una con sitio, esta pantalla gana un
    // selector — no antes, porque no hay con qué probarlo.
    const marca = marcas[0];
    if (!marca) {
      return (
        <p className="text-secondary">
          No hay ninguna marca cargada todavía. Crea una en Organización →
          Marcas antes de editar el sitio.
        </p>
      );
    }

    const filas = await apiFetch<ContenidoFila[]>(
      `/api/v1/storefront/contenido?marca_id=${marca.id}`,
      { token },
    );
    const contenido = Object.fromEntries(
      filas.map((f) => [f.clave, f.valor]),
    ) as Contenido;

    return (
      <ContenidoCliente marcaId={marca.id} nombreMarca={marca.nombre} contenido={contenido} />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el sitio web."
        : "No se pudo cargar el contenido del sitio web.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
