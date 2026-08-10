import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  UnidadesCliente,
  type CategoriaUdm,
  type UnidadMedida,
} from "./unidades-cliente";

export default async function UnidadesMedidaPage() {
  const { token } = await obtenerSesion();

  let unidades: UnidadMedida[];
  let magnitudes: CategoriaUdm[];
  try {
    [unidades, magnitudes] = await Promise.all([
      apiFetch<UnidadMedida[]>("/api/v1/inventory/unidades-medida", { token }),
      apiFetch<CategoriaUdm[]>("/api/v1/inventory/categorias-udm", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las unidades de medida."
        : "No se pudo cargar el catálogo de unidades de medida.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <UnidadesCliente unidades={unidades} magnitudes={magnitudes} />;
}
