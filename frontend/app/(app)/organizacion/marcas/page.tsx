import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { MarcasCliente, type Marca } from "./marcas-cliente";

export default async function MarcasPage() {
  const { token } = await obtenerSesion();

  let marcas: Marca[];
  try {
    marcas = await apiFetch<Marca[]>("/api/v1/marcas", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las marcas."
        : "No se pudieron cargar las marcas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <MarcasCliente marcas={marcas} />;
}
