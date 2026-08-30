import Link from "next/link";

import { ApiError, apiFetch } from "@/lib/api";
import { fechaHora } from "@/lib/fechas";
import { obtenerSesion } from "@/lib/sesion";

/**
 * Ficha de una devolución: qué se devolvió, por qué, a dónde fue y quién la
 * registró o anuló.
 *
 * Existe porque una devolución mueve stock real: la tabla dice que pasó
 * algo, y esto dice **qué** — que es lo que se necesita para auditarla.
 */

type ItemDevolucion = {
  id: string;
  sku_id: string;
  cantidad: string;
  lote_id: string | null;
};

type DevolucionDetalle = {
  id: string;
  almacen_id: string;
  origen: string;
  motivo: string;
  destino: string | null;
  estado: string;
  reporte_dirigido_a: string;
  observacion: string | null;
  registrado_por: string | null;
  anulado_por: string | null;
  anulada_at: string | null;
  items: ItemDevolucion[];
};

type Sku = { id: string; codigo: string; articulo_nombre: string };

function Dato({ etiqueta, valor }: { etiqueta: string; valor: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-gray">{etiqueta}</dt>
      <dd className="text-sm text-dark">{valor ?? "—"}</dd>
    </div>
  );
}

export default async function DevolucionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token } = await obtenerSesion();
  const { id } = await params;

  let devolucion: DevolucionDetalle;
  try {
    devolucion = await apiFetch<DevolucionDetalle>(
      `/api/v1/inventory/devoluciones/${id}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 404
        ? "Esa devolución no existe."
        : "No se pudo cargar la devolución.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const skus = await apiFetch<Sku[]>("/api/v1/inventory/skus", { token }).catch(
    () => [] as Sku[],
  );
  const nombreDe = new Map(skus.map((s) => [s.id, s.articulo_nombre]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link href="/inventario/devoluciones" className="text-xs text-primary underline">
          ← Devoluciones
        </Link>
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Devolución {devolucion.origen === "proveedor" ? "a proveedor" : "de cliente"}
        </h1>
      </div>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Dato etiqueta="Estado" valor={devolucion.estado} />
        <Dato etiqueta="Motivo" valor={devolucion.motivo} />
        <Dato etiqueta="Destino" valor={devolucion.destino ?? "—"} />
        <Dato etiqueta="Reporte dirigido a" valor={devolucion.reporte_dirigido_a} />
        <Dato etiqueta="Registrada por" valor={devolucion.registrado_por ?? "—"} />
        <Dato
          etiqueta="Anulada"
          valor={
            devolucion.anulada_at
              ? fechaHora(devolucion.anulada_at)
              : "—"
          }
        />
      </dl>

      {devolucion.observacion && (
        <p className="text-sm text-dark">
          <span className="text-xs uppercase tracking-wide text-gray">Observación</span>
          <br />
          {devolucion.observacion}
        </p>
      )}

      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-sm uppercase text-dark">Qué se devolvió</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-borde text-left text-xs uppercase text-gray">
              <th className="py-2">Artículo</th>
              <th className="py-2 text-right">Cantidad</th>
              <th className="py-2">Lote</th>
            </tr>
          </thead>
          <tbody>
            {devolucion.items.map((i) => (
              <tr key={i.id} className="border-b border-borde/50">
                <td className="py-2">{nombreDe.get(i.sku_id) ?? i.sku_id}</td>
                <td className="py-2 text-right font-mono">{Number(i.cantidad)}</td>
                <td className="py-2 text-xs text-gray">{i.lote_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
