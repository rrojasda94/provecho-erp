import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ProveedoresCliente, type Proveedor } from "./proveedores-cliente";

export default async function ProveedoresPage() {
  const { token } = await obtenerSesion();

  try {
    const proveedores = await apiFetch<Proveedor[]>("/api/v1/purchases/proveedores", { token });
    return <ProveedoresCliente proveedores={proveedores} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver proveedores."
        : "No se pudo cargar la lista de proveedores.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
