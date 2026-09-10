import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Activo } from "../activos/activos-cliente";
import { DocumentosCliente, type Documento } from "./documentos-cliente";

export default async function DocumentosPage() {
  const { token } = await obtenerSesion();

  let documentos: Documento[];
  let activos: Activo[] = [];
  try {
    [documentos, activos] = await Promise.all([
      apiFetch<Documento[]>("/api/v1/assets/documentos", { token }),
      apiFetch<Pagina<Activo>>("/api/v1/assets/activos?page_size=200", { token })
        .then((p) => p.items)
        .catch(() => [] as Activo[]),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver documentos."
        : "No se pudo cargar la lista de documentos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const nombreActivo = new Map(activos.map((a) => [a.id, `${a.id_interno} · ${a.nombre}`]));

  return <DocumentosCliente documentos={documentos} nombreActivo={nombreActivo} />;
}
