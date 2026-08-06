"use client";

import { useActionState, useTransition } from "react";

import { abrirPeriodoAction, cerrarPeriodoAction, type EstadoAsiento } from "../actions";

export type Periodo = {
  id: string;
  anio: number;
  mes: number;
  estado: string;
  fecha_cierre: string | null;
};

const ESTADO_INICIAL: EstadoAsiento = { error: "", ok: false };
const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

function BotonCerrar({ periodo }: { periodo: Periodo }) {
  const [pendiente, startTransition] = useTransition();
  if (periodo.estado !== "abierto") {
    return <span className="text-xs text-gray">{periodo.fecha_cierre?.slice(0, 10) ?? "—"}</span>;
  }
  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={() => startTransition(() => void cerrarPeriodoAction(periodo.id))}
      title="Cerrado, el periodo ya no admite asientos"
      className="text-xs font-semibold text-secondary hover:underline"
    >
      Cerrar
    </button>
  );
}

export function PeriodosCliente({ periodos }: { periodos: Periodo[] }) {
  const [estado, formAction, pendiente] = useActionState(abrirPeriodoAction, ESTADO_INICIAL);
  // El mes en curso como valor por defecto: es el que se abre el 99% de las
  // veces, y el `hoy` del navegador alcanza para proponerlo.
  const hoy = new Date();

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Periodos contables</h1>
      <p className="text-sm text-gray">
        Un asiento solo entra en un periodo <strong>abierto</strong> — por eso el primer
        asiento de una empresa nueva falla hasta abrir su mes. Cerrar un periodo lo
        congela: nada más se registra ahí.
      </p>

      <form
        action={formAction}
        className="flex flex-wrap items-end gap-3 rounded border border-gray/20 bg-white p-4"
      >
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Año
          <input
            name="anio"
            type="number"
            min={2000}
            max={2100}
            defaultValue={hoy.getFullYear()}
            className="w-28 rounded border border-gray/40 px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Mes
          <select
            name="mes"
            defaultValue={hoy.getMonth() + 1}
            className="rounded border border-gray/40 px-2 py-1"
          >
            {MESES.map((nombre, i) => (
              <option key={nombre} value={i + 1}>
                {nombre}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={pendiente}
          className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
        >
          {pendiente ? "Abriendo..." : "Abrir periodo"}
        </button>
        {estado.error && (
          <p role="alert" className="text-sm font-semibold text-secondary">
            {estado.error}
          </p>
        )}
      </form>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Periodo</th>
            <th className="py-2 pr-4 font-semibold">Estado</th>
            <th className="py-2 font-semibold">Cierre</th>
          </tr>
        </thead>
        <tbody>
          {periodos.length === 0 && (
            <tr>
              <td colSpan={3} className="py-3 text-gray">
                Sin periodos abiertos todavía.
              </td>
            </tr>
          )}
          {periodos.map((p) => (
            <tr key={p.id} className="border-b border-gray/15">
              <td className="py-2 pr-4 font-semibold text-dark">
                {MESES[p.mes - 1]} {p.anio}
              </td>
              <td className="py-2 pr-4">
                <span
                  className={
                    p.estado === "abierto"
                      ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                      : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
                  }
                >
                  {p.estado}
                </span>
              </td>
              <td className="py-2">
                <BotonCerrar periodo={p} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
