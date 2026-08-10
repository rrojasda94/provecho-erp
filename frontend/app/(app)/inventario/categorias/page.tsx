import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { CategoriasCliente, type Categoria, type ProgramaConteo } from "./categorias-cliente";

type Params = Promise<{ categoria?: string }>;

export default async function CategoriasPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const { categoria } = await searchParams;

  let categorias: Categoria[];
  try {
    categorias = await apiFetch<Categoria[]>("/api/v1/inventory/categorias", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo."
        : "No se pudieron cargar las categorías.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El programa de conteo es contexto: sin él la pantalla sigue diciendo qué
  // categorías hay y cada cuánto se cuentan.
  const programa = await apiFetch<ProgramaConteo[]>(
    "/api/v1/inventory/conteos/programa",
    { token },
  ).catch(() => []);

  return (
    <CategoriasCliente
      categorias={categorias}
      programa={programa}
      resaltado={categoria ?? null}
    />
  );
}
