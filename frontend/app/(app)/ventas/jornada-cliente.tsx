"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { anularVentaAction, reintentarComprobanteAction } from "./actions";

export type Venta = {
  id: string;
  fecha_orden: string;
  numero_orden: number;
  canal: string;
  modalidad: string;
  estado: string;
  total: string;
  referencia_atencion: string | null;
};
export type Comprobante = {
  id: string;
  tipo: string;
  serie: string;
  correlativo: number;
  estado_emision: string;
  detalle_emision: string | null;
  intentos_emision: number;
};
export type Sucursal = { id: string; nombre: string };

const ESTADOS = ["orden", "pagada", "entregada", "anulada"];

function EstadoVenta({ estado }: { estado: string }) {
  const clase =
    estado === "anulada"
      ? "bg-gray/20 text-gray"
      : estado === "orden"
        ? "bg-secondary/15 text-secondary"
        : "bg-accent/30 text-dark";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
      {estado}
    </span>
  );
}

function CeldaComprobante({ comprobante }: { comprobante?: Comprobante }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");

  if (!comprobante) {
    return <span className="text-xs text-gray">sin cuenta cerrada</span>;
  }

  const fallo = comprobante.estado_emision === "rechazado" || comprobante.estado_emision === "error";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs font-semibold text-dark">
        {comprobante.tipo} {comprobante.serie}-{comprobante.correlativo}
      </span>
      <span className={`text-xs ${fallo ? "text-secondary" : "text-gray"}`}>
        {comprobante.estado_emision}
        {comprobante.intentos_emision > 1 && ` · ${comprobante.intentos_emision} intentos`}
      </span>
      {fallo && (
        <>
          <button
            type="button"
            disabled={pendiente}
            onClick={() =>
              startTransition(async () => {
                const r = await reintentarComprobanteAction(comprobante.id);
                setError(r.error);
              })
            }
            className="self-start text-xs font-bold text-primary hover:underline"
          >
            {pendiente ? "Reintentando..." : "Reintentar emisión"}
          </button>
          {(error || comprobante.detalle_emision) && (
            <span className="text-xs text-secondary">
              {error || comprobante.detalle_emision}
            </span>
          )}
        </>
      )}
    </div>
  );
}

function BotonAnular({ venta }: { venta: Venta }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  // Anular repone el stock y solo aplica antes de cobrar: una venta pagada se
  // corrige con nota de crédito, no borrándola.
  if (venta.estado !== "orden") return <span className="text-xs text-gray">—</span>;
  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => {
            const r = await anularVentaAction(venta.id);
            setError(r.error);
          })
        }
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Anulando..." : "Anular"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </div>
  );
}

export function JornadaCliente({
  ventas,
  comprobantes,
  sucursales,
  sucursalId,
  fecha,
  estado,
}: {
  ventas: Venta[];
  comprobantes: Record<string, Comprobante>;
  sucursales: Sucursal[];
  sucursalId: string;
  fecha: string;
  estado: string;
}) {
  const router = useRouter();

  // Los filtros viven en la URL, no en estado del cliente: la jornada de una
  // sucursal en una fecha es una dirección que se comparte y se recarga.
  const navegar = (cambios: Record<string, string>) => {
    const query = new URLSearchParams({ sucursal: sucursalId, fecha, estado, ...cambios });
    for (const [k, v] of [...query]) if (!v) query.delete(k);
    router.push(`/ventas?${query}`);
  };

  const totales = useMemo(() => {
    const cobradas = ventas.filter((v) => v.estado !== "anulada" && v.estado !== "orden");
    return {
      cantidad: cobradas.length,
      monto: cobradas.reduce((t, v) => t + Number(v.total), 0),
      abiertas: ventas.filter((v) => v.estado === "orden").length,
    };
  }, [ventas]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Jornada</h1>
      <p className="text-sm text-gray">
        Lo vendido en una sucursal, día por día: verificar lo cobrado, reintentar el
        comprobante que SUNAT rechazó y anular una orden que nunca se cobró.
      </p>

      <div className="flex flex-wrap items-end gap-3 rounded border border-gray/20 bg-white p-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sucursal
          <select
            value={sucursalId}
            onChange={(e) => navegar({ sucursal: e.target.value })}
            className="rounded border border-gray/40 px-2 py-1"
          >
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Fecha
          <input
            type="date"
            value={fecha}
            onChange={(e) => navegar({ fecha: e.target.value })}
            className="rounded border border-gray/40 px-2 py-1"
          />
          <span className="text-xs font-normal text-gray">Vacío = hoy</span>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Estado
          <select
            value={estado}
            onChange={(e) => navegar({ estado: e.target.value })}
            className="rounded border border-gray/40 px-2 py-1"
          >
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex gap-6 rounded bg-cream px-4 py-3 text-sm">
        <span>
          <strong className="tabular-nums">{totales.cantidad}</strong> ventas cobradas
        </span>
        <span>
          <strong className="tabular-nums">S/ {totales.monto.toFixed(2)}</strong> en total
        </span>
        <span className={totales.abiertas > 0 ? "text-secondary" : "text-gray"}>
          <strong className="tabular-nums">{totales.abiertas}</strong> sin cobrar
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
              <th className="py-2 pr-4 font-semibold">Orden</th>
              <th className="py-2 pr-4 font-semibold">Canal / modalidad</th>
              <th className="py-2 pr-4 font-semibold">Atención</th>
              <th className="py-2 pr-4 font-semibold">Total</th>
              <th className="py-2 pr-4 font-semibold">Estado</th>
              <th className="py-2 pr-4 font-semibold">Comprobante</th>
              <th className="py-2 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {ventas.length === 0 && (
              <tr>
                <td colSpan={7} className="py-3 text-gray">
                  No hay ventas en esa jornada.
                </td>
              </tr>
            )}
            {ventas.map((v) => (
              <tr key={v.id} className="border-b border-gray/15 align-top">
                <td className="py-2 pr-4 font-semibold text-dark tabular-nums">
                  #{v.numero_orden}
                </td>
                <td className="py-2 pr-4">
                  {v.canal} · {v.modalidad}
                </td>
                <td className="py-2 pr-4">{v.referencia_atencion ?? "—"}</td>
                <td className="py-2 pr-4 tabular-nums">S/ {v.total}</td>
                <td className="py-2 pr-4">
                  <EstadoVenta estado={v.estado} />
                </td>
                <td className="py-2 pr-4">
                  <CeldaComprobante comprobante={comprobantes[v.id]} />
                </td>
                <td className="py-2">
                  <BotonAnular venta={v} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
