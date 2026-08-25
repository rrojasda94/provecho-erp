import { ApiError, apiFetch } from "@/lib/api";
import type { Atributo } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { AtributosCliente } from "./atributos-cliente";

export default async function AtributosPage() {
  const { token } = await obtenerSesion();

  try {
    const atributos = await apiFetch<Atributo[]>("/api/v1/sales/atributos", { token });
    return <AtributosCliente inicial={atributos} />;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo comercial."
        : "No se pudieron cargar los atributos.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
