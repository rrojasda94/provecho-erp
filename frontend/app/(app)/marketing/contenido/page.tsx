import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ContenidoCliente, type Pieza } from "./contenido-cliente";
import type { Campana, Marca } from "../campanas-cliente";

export default async function ContenidoPage() {
  const { token } = await obtenerSesion();

  try {
    const [piezas, campanas, marcas] = await Promise.all([
      apiFetch<Pagina<Pieza>>("/api/v1/marketing/piezas", { token }),
      // Sin `page_size`, el desplegable de campaña se queda en las primeras
      // 50 sin decirlo.
      apiFetch<Pagina<Campana>>("/api/v1/marketing/campanas?page_size=200", {
        token,
      }),
      apiFetch<Marca[]>("/api/v1/marcas", { token }),
    ]);
    return (
      <ContenidoCliente
        piezas={piezas.items}
        campanas={campanas.items}
        marcas={marcas}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el contenido."
        : "No se pudo cargar el calendario de contenido.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
