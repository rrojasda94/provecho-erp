import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ClientesCliente, type ClienteWeb } from "./clientes-cliente";

export default async function WebClientesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { token } = await obtenerSesion();
  const { q } = await searchParams;

  try {
    const clientes = await apiFetch<ClienteWeb[]>(
      `/api/v1/storefront/clientes?q=${encodeURIComponent(q ?? "")}`,
      { token },
    );
    return <ClientesCliente clientes={clientes} busqueda={q ?? ""} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los clientes del sitio web."
        : "No se pudieron cargar los clientes del sitio web.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
