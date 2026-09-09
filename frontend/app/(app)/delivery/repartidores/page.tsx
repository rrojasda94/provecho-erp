import { ApiError, apiFetch } from "@/lib/api";
import type { Repartidor, RepartidorCandidato } from "@/lib/delivery";
import { obtenerSesion } from "@/lib/sesion";

import RepartidoresCliente from "./repartidores-cliente";

type SucursalOpcion = { id: string; nombre: string };

export default async function RepartidoresPage() {
  const { token, usuario } = await obtenerSesion();

  let repartidores: Repartidor[];
  try {
    repartidores = await apiFetch<Repartidor[]>("/api/v1/delivery/repartidores", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver repartidores."
        : "No se pudo cargar la lista de repartidores.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Candidatos y sucursales solo sirven para el diálogo de alta — si el
  // usuario no tiene `delivery.gestionar_repartidores` ninguna de las dos
  // llamadas corre, y si una falla igual se ve la lista de arriba.
  let candidatos: RepartidorCandidato[] = [];
  let sucursales: SucursalOpcion[] = [];
  if (usuario.empresa_id) {
    candidatos = await apiFetch<RepartidorCandidato[]>(
      `/api/v1/delivery/repartidores/candidatos?empresa_id=${usuario.empresa_id}`,
      { token },
    ).catch(() => []);
  }
  if (usuario.sucursales.length > 0) {
    sucursales = await apiFetch<SucursalOpcion[]>("/api/v1/sucursales", { token })
      .then((todas) => todas.filter((s) => usuario.sucursales.includes(s.id)))
      .catch(() => []);
  }

  return (
    <RepartidoresCliente
      repartidores={repartidores}
      candidatos={candidatos}
      sucursales={sucursales}
      permisos={usuario.permisos}
    />
  );
}
