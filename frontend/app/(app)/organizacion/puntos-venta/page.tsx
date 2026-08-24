import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  PuntosVentaCliente,
  type PuntoVenta,
  type Sucursal,
} from "./puntos-venta-cliente";

export default async function PuntosVentaPage() {
  const { token } = await obtenerSesion();

  let puntos: PuntoVenta[];
  let sucursales: Sucursal[];
  try {
    // Sin `sucursal_id` el listado trae las de toda la empresa, que es lo que
    // pide una pantalla de administración.
    [puntos, sucursales] = await Promise.all([
      apiFetch<PuntoVenta[]>("/api/v1/sales/puntos-venta", { token }),
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los puntos de venta."
        : "No se pudieron cargar los puntos de venta.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <PuntosVentaCliente puntos={puntos} sucursales={sucursales} />;
}
