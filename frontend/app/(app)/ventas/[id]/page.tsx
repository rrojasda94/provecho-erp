import Link from "next/link";

import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type Venta = {
  id: string;
  sucursal_id: string;
  fecha_orden: string;
  numero_orden: number;
  canal: string;
  modalidad: string;
  estado: string;
  total: string;
  referencia_atencion: string | null;
  comensales: number | null;
  descuento_modo: string | null;
  descuento_valor: string | null;
  descuento_motivo: string | null;
  tipo: string;
  consumo_motivo: string | null;
};

type VentaItem = {
  id: string;
  nombre: string;
  cantidad: string;
  precio_unitario: string;
  grupo_cobro: number;
};

/**
 * Ficha de una venta. Es a donde llevan las cuatro emisiones de `sales`
 * —pedido demorado, descuento aplicado, venta anulada, líneas anuladas— y
 * las filas de `pedidos_demorados` en el tablero (ADR-036).
 *
 * Solo lectura: cobrar, anular y entregar viven en el PDV, que es donde está
 * el contexto (y el PIN del supervisor) para hacerlo.
 */
export default async function VentaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  let venta: Venta;
  try {
    venta = await apiFetch<Venta>(`/api/v1/sales/ventas/${id}`, { token });
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    const mensaje =
      status === 403
        ? "Esa venta está fuera de tu alcance."
        : status === 404
          ? "Esa venta no existe."
          : "No se pudo cargar la venta.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const items = await apiFetch<VentaItem[]>(
    `/api/v1/sales/ventas/${id}/items`,
    { token },
  ).catch(() => []);

  const datos: [string, string][] = [
    ["Estado", venta.estado],
    ["Fecha", venta.fecha_orden],
    ["Canal", venta.canal],
    ["Modalidad", venta.modalidad],
    ["Total", venta.total],
    ["Atención", venta.referencia_atencion ?? "—"],
  ];

  return (
    <section className="flex flex-col gap-6">
      <Link
        href={`/ventas?sucursal=${venta.sucursal_id}&fecha=${venta.fecha_orden}`}
        className="text-sm font-semibold text-primary hover:underline"
      >
        ← Jornada
      </Link>
      <h1 className="font-heading text-xl italic uppercase text-dark">
        Pedido #{venta.numero_orden}
      </h1>

      <dl className="grid gap-4 rounded border border-gray/20 p-4 sm:grid-cols-3">
        {datos.map(([etiqueta, valor]) => (
          <div key={etiqueta} className="flex flex-col gap-0.5">
            <dt className="text-xs font-bold uppercase text-gray">{etiqueta}</dt>
            <dd className="text-sm text-dark">{valor}</dd>
          </div>
        ))}
      </dl>

      {venta.descuento_modo && (
        <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
          Descuento {venta.descuento_modo} de {venta.descuento_valor}
          {venta.descuento_motivo ? ` — ${venta.descuento_motivo}` : ""}
        </p>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-gray">Líneas</h2>
        {items.length === 0 ? (
          <p className="text-sm text-secondary">Sin líneas para mostrar.</p>
        ) : (
          <div className="overflow-x-auto rounded border border-gray/20">
            <table className="w-full text-sm">
              <thead className="bg-cream text-left text-xs uppercase text-gray">
                <tr>
                  <th className="px-3 py-2">Producto</th>
                  <th className="px-3 py-2">Cantidad</th>
                  <th className="px-3 py-2">Precio</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.id} className="border-t border-gray/10">
                    <td className="px-3 py-2">{i.nombre}</td>
                    <td className="px-3 py-2">{i.cantidad}</td>
                    <td className="px-3 py-2">{i.precio_unitario}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
