"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { primeroElDe } from "@/lib/destinos";

export type Devolucion = {
  id: string;
  almacen_id: string;
  origen: string;
  referencia_id: string | null;
  motivo: string;
  destino: string | null;
  estado: string;
  reporte_dirigido_a: string;
  observacion: string | null;
};

/** Destino de `inventory.devolucion_a_proveedor` y `_de_cliente` (ADR-036).
 * Solo lectura: registrar y anular una devolución tienen su propio flujo. */
export function DevolucionesCliente({
  devoluciones,
  resaltado,
}: {
  devoluciones: Devolucion[];
  resaltado: string | null;
}) {
  const columnas = useMemo<ColumnDef<Devolucion>[]>(
    () => [
      { header: "Origen", accessorKey: "origen" },
      { header: "Motivo", accessorKey: "motivo" },
      {
        header: "Destino",
        accessorKey: "destino",
        cell: ({ row }) => row.original.destino ?? "—",
      },
      { header: "Dirigida a", accessorKey: "reporte_dirigido_a" },
      { header: "Estado", accessorKey: "estado" },
      {
        header: "Observación",
        accessorKey: "observacion",
        cell: ({ row }) => row.original.observacion ?? "—",
      },
    ],
    [],
  );

  const ordenadas = useMemo(
    () => primeroElDe(devoluciones, resaltado, (d) => d.id),
    [devoluciones, resaltado],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Devoluciones</h1>
      <TablaDatos
        columnas={columnas}
        datos={ordenadas}
        placeholderBusqueda="Buscar por motivo u origen..."
      />
    </div>
  );
}
