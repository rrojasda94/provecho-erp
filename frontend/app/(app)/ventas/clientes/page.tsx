import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ClientesCliente, type Cliente } from "./clientes-cliente";

export default async function ClientesPage() {
  const { token } = await obtenerSesion();

  let clientes: Cliente[];
  try {
    clientes = (
      await apiFetch<Pagina<Cliente>>("/api/v1/sales/clientes/listado?page_size=200", {
        token,
      })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los clientes."
        : "No se pudo cargar el padrón de clientes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return <ClientesCliente clientes={clientes} />;
}
