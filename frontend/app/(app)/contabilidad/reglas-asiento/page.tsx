import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Cuenta } from "../asientos-cliente";
import { ReglasCliente, type Regla } from "./reglas-cliente";

export default async function ReglasAsientoPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [reglas, cuentas] = await Promise.all([
      apiFetch<Regla[]>("/api/v1/accounting/reglas-asiento", { token }),
      apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", { token }),
    ]);
    return (
      <ReglasCliente reglas={reglas} cuentas={cuentas} permisos={usuario.permisos} />
    );
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver la configuración contable."
          : "No se pudieron cargar las reglas de asiento."}
      </p>
    );
  }
}
