import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  PlantillasCliente,
  type Categoria,
  type Marca,
  type Plantilla,
  type Sucursal,
  type Usuario,
} from "./plantillas-cliente";

export default async function PlantillasPage() {
  const { token } = await obtenerSesion();

  let plantillas: Plantilla[];
  try {
    plantillas = (
      await apiFetch<Pagina<Plantilla>>("/api/v1/supervision/plantillas", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para gestionar plantillas de supervisión."
        : "No se pudieron cargar las plantillas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const [categorias, sucursales, marcas, usuarios] = await Promise.all([
    apiFetch<Categoria[]>("/api/v1/supervision/categorias", { token }).catch(
      () => [] as Categoria[],
    ),
    apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(() => [] as Sucursal[]),
    apiFetch<Marca[]>("/api/v1/marcas", { token }).catch(() => [] as Marca[]),
    apiFetch<Pagina<Usuario>>("/api/v1/users?page_size=200", { token })
      .then((p) => p.items)
      .catch(() => [] as Usuario[]),
  ]);

  return (
    <PlantillasCliente
      plantillas={plantillas}
      categorias={categorias}
      sucursales={sucursales}
      marcas={marcas}
      usuarios={usuarios}
    />
  );
}
