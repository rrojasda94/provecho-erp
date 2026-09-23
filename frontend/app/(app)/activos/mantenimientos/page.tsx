import { ApiError, apiFetchCompleto } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Activo } from "../activos/activos-cliente";
import { MantenimientosCliente, type OrdenMantenimiento } from "./mantenimientos-cliente";

export default async function MantenimientosPage() {
  const { token } = await obtenerSesion();

  let ordenes: OrdenMantenimiento[];
  let activos: Activo[] = [];
  try {
    [ordenes, activos] = await Promise.all([
      apiFetchCompleto<OrdenMantenimiento>(
        "/api/v1/assets/ordenes-mantenimiento",
        { token },
      ).then((p) => p.items),
      apiFetchCompleto<Activo>("/api/v1/assets/activos", { token })
        .then((p) => p.items)
        .catch(() => [] as Activo[]),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver mantenimientos."
        : "No se pudo cargar la lista de mantenimientos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const nombreActivo = new Map(activos.map((a) => [a.id, `${a.id_interno} · ${a.nombre}`]));

  return <MantenimientosCliente ordenes={ordenes} nombreActivo={nombreActivo} />;
}
