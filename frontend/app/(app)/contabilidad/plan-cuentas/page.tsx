import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { PlanCuentasCliente } from "./plan-cuentas-cliente";
import type { Cuenta } from "../asientos-cliente";

export default async function PlanCuentasPage() {
  const { token } = await obtenerSesion();

  try {
    const cuentas = await apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", {
      token,
    });
    return <PlanCuentasCliente cuentas={cuentas} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el plan de cuentas."
        : "No se pudo cargar el plan de cuentas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
