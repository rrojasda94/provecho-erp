import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { EncuestasCliente, type Encuesta } from "./encuestas-cliente";

/**
 * Qué dijeron los clientes.
 *
 * No había listado: una encuesta solo se podía mirar sabiendo su id o el de su
 * venta, así que las respuestas quedaban donde nadie las leía — y una encuesta
 * que nadie lee es una molestia al cliente sin contrapartida.
 */
export default async function EncuestasPage({
  searchParams,
}: {
  searchParams: Promise<{ estado?: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { estado = "" } = await searchParams;

  const query = new URLSearchParams({ page_size: "100" });
  if (estado) query.set("estado", estado);

  try {
    const pagina = await apiFetch<Pagina<Encuesta>>(
      `/api/v1/marketing/encuestas?${query}`,
      { token },
    );
    return (
      <EncuestasCliente
        encuestas={pagina.items}
        total={pagina.total}
        permisos={usuario.permisos}
      />
    );
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver las encuestas."
          : "No se pudieron cargar las encuestas."}
      </p>
    );
  }
}
