import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ComprobantesCliente, type ComprobanteEmitido } from "./comprobantes-cliente";

/**
 * Registro de ventas: los comprobantes que la empresa emitió.
 *
 * Vive en Contabilidad y consulta `sales` porque el documento fuente del
 * asiento es de ventas — el módulo dueño del dato no cambia por quién lo
 * mira (RN-REP-002). El endpoint acepta `accounting.leer`, así que el
 * contador entra sin que haya que darle el módulo de ventas entero.
 *
 * Por defecto trae **el día de hoy**: es lo que se revisa a diario. El rango
 * se abre con `?desde`/`?hasta`, que es como el contador cierra un mes.
 */
export default async function ComprobantesPage({
  searchParams,
}: {
  searchParams: Promise<{ desde?: string; hasta?: string }>;
}) {
  const { token } = await obtenerSesion();
  const { desde, hasta } = await searchParams;

  const filtros = new URLSearchParams({ page_size: "200" });
  if (desde) filtros.set("desde", desde);
  if (hasta) filtros.set("hasta", hasta);

  try {
    const pagina = await apiFetch<Pagina<ComprobanteEmitido>>(
      `/api/v1/sales/comprobantes?${filtros}`,
      { token },
    );
    return (
      <ComprobantesCliente
        comprobantes={pagina.items}
        total={pagina.total}
        desde={desde ?? null}
        hasta={hasta ?? null}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los comprobantes emitidos."
        : "No se pudieron cargar los comprobantes emitidos.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
