import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { PeriodosCliente, type Periodo } from "./periodos-cliente";

export default async function PeriodosPage() {
  const { token } = await obtenerSesion();

  try {
    const periodos = await apiFetch<Periodo[]>("/api/v1/accounting/periodos", { token });
    return <PeriodosCliente periodos={periodos} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los periodos contables."
        : "No se pudieron cargar los periodos contables.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
