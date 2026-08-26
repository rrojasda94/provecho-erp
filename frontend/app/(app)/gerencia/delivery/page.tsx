import { ApiError, apiFetch } from "@/lib/api";
import { configMapas } from "@/lib/mapas";
import { obtenerSesion } from "@/lib/sesion";

import {
  DeliveryCliente,
  type ConfiguracionDelivery,
  type PropuestaDelivery,
} from "./delivery-cliente";

const CODIGOS = [
  "delivery_tarifa_base",
  "delivery_precio_por_km",
  "delivery_radio_km",
  "delivery_distritos_restringidos",
];

/** Tarifa del delivery (ADR-067).
 *
 * Dos llamadas y no una: `/sales/delivery/configuracion` dice con qué números
 * se está **cobrando** (lo aprobado, o la semilla del `.env`), y
 * `/parametros` dice qué hay **propuesto y sin resolver**. Son dos preguntas
 * distintas y mezclarlas es lo que haría que la pantalla muestre un valor que
 * nadie está usando.
 */
export default async function DeliveryPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [configuracion, parametros] = await Promise.all([
      apiFetch<ConfiguracionDelivery>("/api/v1/sales/delivery/configuracion", { token }),
      apiFetch<(PropuestaDelivery & { estado: string })[]>(
        "/api/v1/parametros?modulo=sales&estado=propuesto",
        { token },
      ),
    ]);
    return (
      <DeliveryCliente
        configuracion={configuracion}
        pendientes={parametros.filter((p) => CODIGOS.includes(p.codigo))}
        empresaId={usuario.empresa_id ?? ""}
        conMapa={Boolean(configMapas().apiKey)}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "La tarifa del delivery la fija Gerencia: hace falta el permiso de parámetros."
        : "No se pudo cargar la tarifa del delivery.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
