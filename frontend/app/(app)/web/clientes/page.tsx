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
    // El estado del correo en paralelo y tolerante: que no se pueda leer no
    // puede dejar sin pantalla a quien está atendiendo a un cliente.
    const [clientes, correo] = await Promise.all([
      apiFetch<ClienteWeb[]>(
        `/api/v1/storefront/clientes?q=${encodeURIComponent(q ?? "")}`,
        { token },
      ),
      apiFetch<{ configurado: boolean }>("/api/v1/storefront/clientes/correo", {
        token,
      }).catch(() => ({ configurado: true })),
    ]);
    return (
      <ClientesCliente
        clientes={clientes}
        busqueda={q ?? ""}
        correoConfigurado={correo.configurado}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los clientes del sitio web."
        : "No se pudieron cargar los clientes del sitio web.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
