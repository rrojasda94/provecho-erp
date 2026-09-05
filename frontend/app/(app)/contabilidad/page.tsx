import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { AsientosCliente, type Asiento, type Cuenta } from "./asientos-cliente";

export default async function AsientosPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [asientos, cuentas] = await Promise.all([
      apiFetch<Pagina<Asiento>>("/api/v1/accounting/asientos", { token }),
      apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", { token }),
    ]);
    return (
      <AsientosCliente
        asientos={asientos.items}
        cuentas={cuentas}
        permisos={usuario.permisos}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el libro contable."
        : "No se pudo cargar el libro contable.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
