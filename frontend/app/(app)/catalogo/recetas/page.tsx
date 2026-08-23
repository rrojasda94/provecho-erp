import { ApiError, apiFetch } from "@/lib/api";
import type { Categoria, Receta, UnidadMedida } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { RecetasCliente } from "./recetas-cliente";

/** Los filtros viajan en la URL y no en estado del cliente: así el listado
 * se filtra **en el servidor** —que es donde están las mil recetas— y un
 * "mandame las subrecetas de lácteos" se comparte pegando el enlace. */
type Params = Promise<{ tipo?: string; categoria?: string }>;

const TIPOS = new Set(["subreceta", "producto"]);

export default async function RecetasPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const { tipo, categoria } = await searchParams;

  const query = new URLSearchParams();
  // Se valida acá y no solo en el servidor para no mandar un `tipo=cualquiera`
  // que vuelve 409 y deja la pantalla en el mensaje de error.
  if (tipo && TIPOS.has(tipo)) query.set("tipo", tipo);
  if (categoria) query.set("categoria_id", categoria);
  // La ruta va literal y el filtro como query aparte: `contrato.test.ts`
  // busca rutas escritas a mano en el código, y una interpolada dentro del
  // string no la puede leer.
  const filtros = query.size ? `?${query}` : "";

  try {
    const [recetas, unidades, categorias] = await Promise.all([
      apiFetch<Receta[]>("/api/v1/inventory/recetas" + filtros, { token }),
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token }),
    ]);
    return (
      <RecetasCliente
        recetas={recetas}
        unidades={unidades}
        categorias={categorias}
        tipo={tipo ?? ""}
        categoria={categoria ?? ""}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las recetas."
        : "No se pudo cargar la lista de recetas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
