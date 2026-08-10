import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { DevolucionesCliente, type Devolucion } from "./devoluciones-cliente";

type Params = Promise<{ devolucion?: string }>;

export default async function DevolucionesPage({
  searchParams,
}: {
  searchParams: Params;
}) {
  const { token } = await obtenerSesion();
  const { devolucion } = await searchParams;

  let devoluciones: Devolucion[];
  try {
    devoluciones = await apiFetch<Devolucion[]>("/api/v1/inventory/devoluciones", {
      token,
    });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las devoluciones."
        : "No se pudieron cargar las devoluciones.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <DevolucionesCliente
      devoluciones={devoluciones}
      resaltado={devolucion ?? null}
    />
  );
}
