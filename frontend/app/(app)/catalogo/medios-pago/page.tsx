import { ApiError, apiFetch } from "@/lib/api";
import type { MedioDePago } from "@/lib/catalogo";
import { obtenerSesion } from "@/lib/sesion";

import { MediosPagoCliente } from "./medios-pago-cliente";

export default async function MediosPagoPage() {
  const { token } = await obtenerSesion();
  let medios: MedioDePago[];

  try {
    // Con los apagados: la pantalla que administra tiene que poder
    // reactivar lo que apagó. El PDV pide aparte, y solo los de cobro.
    medios = await apiFetch<MedioDePago[]>(
      "/api/v1/sales/medios-pago?incluir_inactivos=true",
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el catálogo comercial."
        : "No se pudieron cargar los medios de pago.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Fuera del `try`: la excepción de render de un hijo no la atrapa este
  // bloque, y atraparla acá sería confundir carga con render.
  return <MediosPagoCliente inicial={medios} />;
}
