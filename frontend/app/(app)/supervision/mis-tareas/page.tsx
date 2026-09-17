import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { MisTareasCliente, type TareaInstancia } from "./mis-tareas-cliente";

export default async function MisTareasPage() {
  const { token } = await obtenerSesion();

  let tareas: TareaInstancia[];
  try {
    tareas = await apiFetch<TareaInstancia[]>("/api/v1/supervision/tareas/mias", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene tareas de supervisión asignables."
        : "No se pudieron cargar tus tareas de hoy.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <MisTareasCliente tareas={tareas} />;
}
