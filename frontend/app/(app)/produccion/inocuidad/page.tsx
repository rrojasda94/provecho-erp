import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen } from "../ordenes-cliente";
import { InocuidadCliente, type Checklist } from "./inocuidad-cliente";

export default async function InocuidadProduccionPage() {
  const { token } = await obtenerSesion();

  try {
    const [checklists, almacenes] = await Promise.all([
      apiFetch<Pagina<Checklist>>("/api/v1/production/checklists", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
    return (
      <InocuidadCliente
        checklists={checklists.items}
        total={checklists.total}
        almacenes={almacenes}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver la inocuidad de producción."
        : "No se pudo cargar el checklist de inocuidad.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
