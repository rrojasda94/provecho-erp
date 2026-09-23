import { ApiError, apiFetch, apiFetchCompleto } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { TableroCliente, type Categoria, type Sucursal, type TareaInstancia, type Usuario } from "./tablero-cliente";

type Params = Promise<{ sucursal?: string; fecha?: string }>;

function hoyISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default async function TableroPage({ searchParams }: { searchParams: Params }) {
  const { token } = await obtenerSesion();
  const { sucursal, fecha } = await searchParams;
  const fechaActual = fecha ?? hoyISO();

  const sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(
    () => [] as Sucursal[],
  );
  const sucursalActual = sucursal ?? sucursales[0]?.id ?? "";

  let tareas: TareaInstancia[] = [];
  let error: string | null = null;
  if (sucursalActual) {
    try {
      tareas = await apiFetch<TareaInstancia[]>(
        `/api/v1/supervision/tareas?sucursal_id=${sucursalActual}&fecha=${fechaActual}`,
        { token },
      );
    } catch (e) {
      error =
        e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para gestionar tareas de supervisión."
          : "No se pudieron cargar las tareas.";
    }
  }

  const [categorias, usuarios] = await Promise.all([
    apiFetch<Categoria[]>("/api/v1/supervision/categorias", { token }).catch(
      () => [] as Categoria[],
    ),
    apiFetchCompleto<Usuario>("/api/v1/users", { token })
      .then((p) => p.items)
      .catch(() => [] as Usuario[]),
  ]);

  return (
    <TableroCliente
      tareas={tareas}
      error={error}
      sucursales={sucursales}
      sucursalActual={sucursalActual}
      fechaActual={fechaActual}
      categorias={categorias}
      usuarios={usuarios}
    />
  );
}
