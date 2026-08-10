"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { primeroElDe } from "@/lib/destinos";

export type SaldoLote = {
  lote_id: string;
  codigo: string;
  articulo_id: string;
  almacen_id: string;
  sku_id: string;
  cantidad: string;
  estado: string;
  fecha_vencimiento: string | null;
  vencido: boolean;
  por_vencer: boolean;
};

/**
 * Saldo por lote en orden FEFO. Es a donde lleva
 * `inventory.lote_vencido_detectado`: el reporte dice que se bloqueó, acá se
 * ve cuánto quedó bloqueado y en qué almacén (ADR-036).
 */
export function LotesCliente({
  saldos,
  resaltado,
}: {
  saldos: SaldoLote[];
  resaltado: string | null;
}) {
  const columnas = useMemo<ColumnDef<SaldoLote>[]>(
    () => [
      { header: "Lote", accessorKey: "codigo" },
      { header: "Cantidad", accessorKey: "cantidad" },
      {
        header: "Vence",
        accessorKey: "fecha_vencimiento",
        cell: ({ row }) => row.original.fecha_vencimiento ?? "—",
      },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => (
          <span
            className={
              row.original.vencido
                ? "rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900"
                : row.original.por_vencer
                  ? "rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900"
                  : "text-sm text-gray"
            }
          >
            {row.original.vencido
              ? "Vencido"
              : row.original.por_vencer
                ? "Por vencer"
                : row.original.estado}
          </span>
        ),
      },
    ],
    [],
  );

  const ordenados = useMemo(
    () => primeroElDe(saldos, resaltado, (s) => s.lote_id),
    [saldos, resaltado],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Lotes</h1>
      {resaltado && !saldos.some((s) => s.lote_id === resaltado) && (
        <p className="text-sm text-secondary">
          Ese lote ya no tiene saldo en ningún almacén.
        </p>
      )}
      <TablaDatos
        columnas={columnas}
        datos={ordenados}
        placeholderBusqueda="Buscar por código de lote..."
      />
    </div>
  );
}
