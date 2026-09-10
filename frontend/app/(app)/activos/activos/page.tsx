import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ActivosCliente, type Activo } from "./activos-cliente";

export default async function ActivosPage() {
  const { token } = await obtenerSesion();

  let activos: Activo[];
  try {
    activos = (
      await apiFetch<Pagina<Activo>>("/api/v1/assets/activos?page_size=200", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los activos."
        : "No se pudo cargar la lista de activos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <ActivosCliente activos={activos} />;
}
