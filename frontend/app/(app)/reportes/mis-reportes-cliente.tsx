"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { CLASE_NIVEL, type ReporteEmitido } from "@/lib/reports";

export function MisReportesCliente({ reportes }: { reportes: ReporteEmitido[] }) {
  const columnas = useMemo<ColumnDef<ReporteEmitido>[]>(
    () => [
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
          <div>
            <p className="font-semibold">{row.original.titulo}</p>
            {row.original.cuerpo ? (
              <p className="text-sm text-secondary">{row.original.cuerpo}</p>
            ) : null}
          </div>
        ),
      },
      { header: "Hecho", accessorKey: "codigo_emision" },
      {
        header: "Cuándo",
        accessorKey: "emitido_at",
        cell: ({ row }) => new Date(row.original.emitido_at).toLocaleString("es-PE"),
      },
    ],
    [],
  );

  return (
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-xl font-bold">Mis reportes</h1>
        <p className="text-sm text-secondary">
          Lo que el ERP te envió según las reglas de distribución de tu empresa.
        </p>
      </header>
      <TablaDatos
        columnas={columnas}
        datos={reportes}
        placeholderBusqueda="Buscar en mis reportes..."
      />
    </section>
  );
}
