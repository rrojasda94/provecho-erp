import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  ReservasCliente,
  type OpcionAlmacen,
  type OpcionSku,
  type Reserva,
} from "./reservas-cliente";

type Almacen = { id: string; nombre: string };
type Sku = { id: string; codigo: string; articulo_nombre: string };

export default async function ReservasPage() {
  const { token, usuario } = await obtenerSesion();

  let reservas: Reserva[];
  try {
    reservas = await apiFetch<Reserva[]>("/api/v1/inventory/reservas", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las reservas."
        : "No se pudieron cargar las reservas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Solo para poner nombre al almacén y al SKU. Si fallan, la tabla se ve
  // igual con los ids: es peor no ver nada.
  const [almacenes, skus] = await Promise.all([
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => []),
    apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(() => []),
  ]);

  return (
    <ReservasCliente
      reservas={reservas}
      almacenes={almacenes.map((a): OpcionAlmacen => ({ id: a.id, nombre: a.nombre }))}
      skus={skus.map(
        (s): OpcionSku => ({ id: s.id, etiqueta: `${s.articulo_nombre} (${s.codigo})` }),
      )}
      permisos={usuario.permisos}
    />
  );
}
