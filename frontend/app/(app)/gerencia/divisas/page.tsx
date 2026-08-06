import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { DivisasCliente, type DivisaCompleta } from "./divisas-cliente";

export default async function DivisasPage() {
  const { token } = await obtenerSesion();

  try {
    const divisas = await apiFetch<DivisaCompleta[]>("/api/v1/divisas", { token });
    return <DivisasCliente divisas={divisas} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para administrar divisas."
        : "No se pudieron cargar las divisas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
