import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { AlmacenesCliente, type Almacen, type Sucursal } from "./almacenes-cliente";

export default async function AlmacenesPage() {
  const { token } = await obtenerSesion();

  let almacenes: Almacen[];
  let sucursales: Sucursal[];
  try {
    [almacenes, sucursales] = await Promise.all([
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los almacenes."
        : "No se pudieron cargar los almacenes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <AlmacenesCliente almacenes={almacenes} sucursales={sucursales} />;
}
