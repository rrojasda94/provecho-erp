"use client";

import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";

/**
 * Tabla genérica del ERP (F2.11): TanStack Table headless + Tailwind, sin
 * componentes propios que atarse. Alcance v1: orden por columna, búsqueda
 * global, filtro, paginación — lo que ADR-013/frontend-architecture.md
 * definió como suficiente para el primer listado real. v2 (congelar/mover
 * columnas, selección masiva, scroll virtual, totales) se prende con las
 * mismas APIs de TanStack cuando una pantalla lo necesite, no antes.
 */
export function TablaDatos<T>({
  columnas,
  datos,
  placeholderBusqueda = "Buscar...",
}: {
  columnas: ColumnDef<T>[];
  datos: T[];
  placeholderBusqueda?: string;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filtroGlobal, setFiltroGlobal] = useState("");

  const tabla = useReactTable({
    data: datos,
    columns: columnas,
    state: { sorting, globalFilter: filtroGlobal },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFiltroGlobal,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  const filas = tabla.getRowModel().rows;

  return (
    <div>
      <input
        value={filtroGlobal}
        onChange={(e) => setFiltroGlobal(e.target.value)}
        placeholder={placeholderBusqueda}
        aria-label={placeholderBusqueda}
        className="mb-3 w-full max-w-xs"
      />
      <div className="overflow-x-auto rounded border border-gray/20 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-cream">
            {tabla.getHeaderGroups().map((grupo) => (
              <tr key={grupo.id}>
                {grupo.headers.map((header) => {
                  const puedeOrdenar = header.column.getCanSort();
                  const orden = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      onClick={
                        puedeOrdenar ? header.column.getToggleSortingHandler() : undefined
                      }
                      className={`px-3 py-2 text-left font-heading text-xs uppercase tracking-wide text-gray ${
                        puedeOrdenar ? "cursor-pointer select-none hover:text-dark" : ""
                      }`}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {orden === "asc" ? " ↑" : orden === "desc" ? " ↓" : ""}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {filas.length === 0 ? (
              <tr>
                <td colSpan={columnas.length} className="px-3 py-6 text-center text-gray">
                  Sin resultados.
                </td>
              </tr>
            ) : (
              filas.map((fila) => (
                <tr key={fila.id} className="border-t border-gray/10 hover:bg-cream/40">
                  {fila.getVisibleCells().map((celda) => (
                    <td key={celda.id} className="px-3 py-2">
                      {flexRender(celda.column.columnDef.cell, celda.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between text-sm text-gray">
        <span>
          Página {tabla.getState().pagination.pageIndex + 1} de {tabla.getPageCount() || 1} ·{" "}
          {tabla.getFilteredRowModel().rows.length} resultados
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => tabla.previousPage()}
            disabled={!tabla.getCanPreviousPage()}
            className="rounded border border-gray px-2 py-1 disabled:opacity-40"
          >
            ← Anterior
          </button>
          <button
            type="button"
            onClick={() => tabla.nextPage()}
            disabled={!tabla.getCanNextPage()}
            className="rounded border border-gray px-2 py-1 disabled:opacity-40"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </div>
  );
}
