import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { JornadaCliente, type Comprobante, type Sucursal, type Venta } from "./jornada-cliente";

type Params = Promise<{ sucursal?: string; fecha?: string; estado?: string }>;

/** El comprobante se pide por venta: es lo que hace útil la pantalla (ver
 * qué quedó sin emitir), y son las ventas de un día, no un histórico. Un
 * 404 significa que la venta todavía no cerró cuenta — no es un error. */
async function comprobantesDe(
  ventas: Venta[],
  token: string,
): Promise<Record<string, Comprobante>> {
  const pares = await Promise.all(
    ventas.map(async (v) => {
      try {
        const c = await apiFetch<Comprobante>(
          `/api/v1/sales/ventas/${v.id}/comprobante`,
          { token },
        );
        return [v.id, c] as const;
      } catch {
        return null;
      }
    }),
  );
  return Object.fromEntries(pares.filter((p): p is readonly [string, Comprobante] => p !== null));
}

async function jornadaDe(
  sucursalId: string,
  filtros: { fecha?: string; estado?: string },
  token: string,
): Promise<Venta[]> {
  const query = new URLSearchParams({ sucursal_id: sucursalId });
  // Sin fecha, el backend usa hoy en zona del negocio — no la del navegador.
  // La pantalla mira un día y el endpoint acepta rango, así que va el mismo
  // día en las dos puntas; el histórico de varios días espera a que el
  // comprobante deje de pedirse venta por venta (N+1, ver ROADMAP).
  if (filtros.fecha) {
    query.set("desde", filtros.fecha);
    query.set("hasta", filtros.fecha);
  }
  if (filtros.estado) query.set("estado", filtros.estado);
  const pagina = await apiFetch<Pagina<Venta>>(`/api/v1/sales/ventas?${query}`, { token });
  return pagina.items;
}

export default async function VentasPage({ searchParams }: { searchParams: Params }) {
  const { token } = await obtenerSesion();
  const filtros = await searchParams;

  let sucursales: Sucursal[];
  try {
    sucursales = await apiFetch<Sucursal[]>("/api/v1/sucursales", { token });
  } catch {
    return <p className="text-secondary">No se pudieron cargar las sucursales.</p>;
  }
  // La jornada es *de una sucursal*: sin elegirla el endpoint no responde, así
  // que la primera del alcance del usuario es el valor por defecto razonable.
  const sucursalId = filtros.sucursal ?? sucursales[0]?.id;
  if (!sucursalId) {
    return (
      <p className="text-secondary">
        Tu usuario no tiene ninguna sucursal asignada: la jornada se mira por sucursal.
      </p>
    );
  }

  let ventas: Venta[];
  try {
    ventas = await jornadaDe(sucursalId, filtros, token);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Esa sucursal está fuera de tu alcance."
        : "No se pudo cargar la jornada.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <JornadaCliente
      ventas={ventas}
      comprobantes={await comprobantesDe(ventas, token)}
      sucursales={sucursales}
      sucursalId={sucursalId}
      fecha={filtros.fecha ?? ""}
      estado={filtros.estado ?? ""}
    />
  );
}
