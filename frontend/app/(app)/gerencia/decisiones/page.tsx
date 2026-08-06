import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { DecisionesCliente, type Decision } from "./decisiones-cliente";

export default async function DecisionesPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const decisiones = await apiFetch<Decision[]>("/api/v1/decisiones-gerenciales", {
      token,
    });
    return (
      <DecisionesCliente
        decisiones={decisiones}
        // El área ejecutora lee las actas pero no las firma (RN-GER-005):
        // sin `gerencia.decidir` la pantalla es de consulta.
        puedeDecidir={usuario.permisos.some((p) => p === "gerencia.decidir" || p === "*")}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las actas de decisión."
        : "No se pudieron cargar las decisiones gerenciales.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
