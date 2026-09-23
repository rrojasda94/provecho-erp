import { ApiError, apiFetch, apiFetchCompleto } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { InformesCliente, type InformeDiario, type Sucursal } from "./informes-cliente";

export default async function InformesPage() {
  const { token } = await obtenerSesion();

  let informes: InformeDiario[];
  try {
    informes = (
      await apiFetchCompleto<InformeDiario>("/api/v1/supervision/informes", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los informes de supervisión."
        : "No se pudieron cargar los informes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token }).catch(
    () => [] as Sucursal[],
  );

  return <InformesCliente informes={informes} sucursales={sucursales} />;
}
