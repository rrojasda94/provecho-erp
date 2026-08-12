"use client";

import type { Table } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

const TAMANOS = [10, 25, 50, 100];

/**
 * Pie de la tabla: cuántas filas hay, en qué página se está y cómo cambiar de
 * página o de tamaño.
 *
 * El selector de tamaño no estaba y se pedía a gritos: 10 filas fijas obligan
 * a paginar seis veces para revisar un inventario de sesenta artículos, y la
 * pregunta que se hace en almacén ("¿está todo?") no se responde de a diez.
 */
export function TablaPaginacion<T>({ tabla }: { tabla: Table<T> }) {
  const { pageIndex, pageSize } = tabla.getState().pagination;
  const total = tabla.getFilteredRowModel().rows.length;

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>
        <span className="cifra">{total}</span> {total === 1 ? "resultado" : "resultados"} · página{" "}
        <span className="cifra">{pageIndex + 1}</span> de{" "}
        <span className="cifra">{tabla.getPageCount() || 1}</span>
      </span>

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-1.5">
          Filas
          <select
            value={pageSize}
            onChange={(e) => tabla.setPageSize(Number(e.target.value))}
            className="h-7 rounded-md border border-input bg-transparent px-1.5 text-sm"
          >
            {TAMANOS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Página anterior"
            onClick={() => tabla.previousPage()}
            disabled={!tabla.getCanPreviousPage()}
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Página siguiente"
            onClick={() => tabla.nextPage()}
            disabled={!tabla.getCanNextPage()}
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      </div>
    </div>
  );
}
