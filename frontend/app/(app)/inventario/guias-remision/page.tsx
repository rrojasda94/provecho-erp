import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { GuiasRemisionCliente, type GuiaRemision } from "./guias-remision-cliente";

export default async function GuiasRemisionPage() {
  const { token } = await obtenerSesion();

  let guias: GuiaRemision[];
  try {
    guias = (
      await apiFetch<Pagina<GuiaRemision>>("/api/v1/inventory/guias-remision", {
        token,
      })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las guías de remisión."
        : "No se pudieron cargar las guías de remisión.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <GuiasRemisionCliente guias={guias} />;
}
