import { Rastro } from "@/components/shell/rastro";
import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type SkuDetalle = {
  id: string;
  codigo: string;
  codigo_barras: string | null;
  activo: boolean;
  articulo: { id: string; nombre: string; id_interno: string; tipo: string };
  stock: {
    almacen_id: string;
    almacen: string;
    cantidad: string;
    reservado: string;
    disponible: string;
    stock_minimo: string | null;
    bajo_minimo: boolean;
  }[];
};

/**
 * A donde lleva `inventory.stock_bajo_minimo` (ADR-036). El reporte dice que
 * un SKU cruzó su punto de reorden; acá se ve cuánto queda en cada almacén,
 * que es lo que hay que mirar para decidir reponer.
 */
export default async function SkuPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  let sku: SkuDetalle;
  try {
    sku = await apiFetch<SkuDetalle>(`/api/v1/inventory/skus/${id}`, { token });
  } catch (e) {
    const status = e instanceof ApiError ? e.status : 0;
    const mensaje =
      status === 403
        ? "Tu usuario no tiene permiso para ver este SKU."
        : status === 404
          ? "Ese SKU no existe."
          : "No se pudo cargar el SKU.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <section className="flex flex-col gap-6">
      {/* La hoja nombra el SKU y el rastro dice de qué artículo cuelga: desde
          acá, "volver" es al artículo del que uno vino, no al listado. */}
      <Rastro hoja={`${sku.articulo.nombre} · ${sku.codigo}`} />
      <header className="flex flex-col gap-1">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          {sku.articulo.nombre}
        </h1>
        <p className="text-sm text-secondary">
          SKU {sku.codigo}
          {sku.codigo_barras ? ` · código de barras ${sku.codigo_barras}` : ""}
        </p>
      </header>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-gray">Stock por almacén</h2>
        {sku.stock.length === 0 ? (
          <p className="text-sm text-secondary">
            Este SKU no tiene saldo en ningún almacén.
          </p>
        ) : (
          <div className="overflow-x-auto rounded border border-gray/20">
            <table className="w-full text-sm">
              <thead className="bg-cream text-left text-xs uppercase text-gray">
                <tr>
                  <th className="px-3 py-2">Almacén</th>
                  <th className="px-3 py-2">Físico</th>
                  <th className="px-3 py-2">Reservado</th>
                  <th className="px-3 py-2">Disponible</th>
                  <th className="px-3 py-2">Mínimo</th>
                </tr>
              </thead>
              <tbody>
                {sku.stock.map((s) => (
                  <tr key={s.almacen_id} className="border-t border-gray/10">
                    <td className="px-3 py-2">{s.almacen}</td>
                    <td className="px-3 py-2">{s.cantidad}</td>
                    <td className="px-3 py-2">{s.reservado}</td>
                    <td className="px-3 py-2">{s.disponible}</td>
                    <td className="px-3 py-2">
                      {s.stock_minimo ?? "—"}
                      {s.bajo_minimo && (
                        <span className="ml-2 rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
                          Bajo mínimo
                        </span>
                      )}
                    </td>
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
