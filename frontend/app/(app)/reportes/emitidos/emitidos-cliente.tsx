"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { CLASE_NIVEL, type ReporteEmitido } from "@/lib/reports";

export function EmitidosCliente({ reportes }: { reportes: ReporteEmitido[] }) {
  const columnas = useMemo<ColumnDef<ReporteEmitido>[]>(
    () => [
      {
        header: "Cuándo",
        accessorKey: "emitido_at",
        cell: ({ row }) => new Date(row.original.emitido_at).toLocaleString("es-PE"),
      },
      { header: "Hecho", accessorKey: "codigo_emision" },
      {
        header: "Nivel",
        accessorKey: "nivel",
        cell: ({ row }) => (
          <span
            className={`rounded px-2 py-0.5 text-xs font-bold ${
              CLASE_NIVEL[row.original.nivel] ?? ""
            }`}
          >
            {row.original.nivel}
          </span>
        ),
      },
      {
        header: "Reporte",
        accessorKey: "titulo",
        cell: ({ row }) => (
          <Link
            href={`/reportes/emitidos/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {row.original.titulo}
          </Link>
        ),
      },
      { header: "Quién", accessorKey: "actor" },
    ],
    [],
  );

  return (
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-xl font-bold">Reportes emitidos</h1>
        <p className="text-sm text-secondary">
          Todo lo que el ERP reportó en tu empresa, le haya llegado a alguien o no.
        </p>
      </header>
      <TablaDatos
        columnas={columnas}
        datos={reportes}
        placeholderBusqueda="Buscar por hecho o título..."
      />
    </section>
  );
}
