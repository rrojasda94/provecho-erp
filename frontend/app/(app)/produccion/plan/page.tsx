import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen, Articulo } from "../ordenes-cliente";
import { PlanCliente, type Plan } from "./plan-cliente";

export default async function PlanProduccionPage() {
  const { token } = await obtenerSesion();

  try {
    const [planes, almacenes, articulos] = await Promise.all([
      apiFetch<Pagina<Plan>>("/api/v1/production/planes", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
      apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", { token }),
    ]);
    return (
      <PlanCliente
        planes={planes.items}
        total={planes.total}
        almacenes={almacenes}
        articulos={articulos.items}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para planificar producción."
        : "No se pudo cargar el plan de producción.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
