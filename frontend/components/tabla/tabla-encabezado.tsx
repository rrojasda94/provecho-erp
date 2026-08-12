"use client";

import type { Table } from "@tanstack/react-table";
import { flexRender } from "@tanstack/react-table";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

/**
 * Encabezado de la tabla. Vive en su propio archivo por el límite de
 * complejidad del lint (10): con el orden, la alineación numérica y el
 * pegado, `tabla-datos.tsx` lo pasaba.
 *
 * `sticky`: las tablas del ERP son largas (movimientos de stock, asientos,
 * planilla) y a la tercera pantalla de scroll nadie recuerda qué columna es
 * cuál. La sombra aparece sola porque el encabezado queda por encima de las
 * filas, no porque haya un listener de scroll.
 */
export function TablaEncabezado<T>({ tabla }: { tabla: Table<T> }) {
  return (
    <thead className="sticky top-0 z-10 bg-muted/70 backdrop-blur-sm">
      {tabla.getHeaderGroups().map((grupo) => (
        <tr key={grupo.id}>
          {grupo.headers.map((header) => {
            const puedeOrdenar = header.column.getCanSort();
            const orden = header.column.getIsSorted();
            const numero = header.column.columnDef.meta?.numero;

            return (
              <th
                key={header.id}
                aria-sort={
                  orden === "asc" ? "ascending" : orden === "desc" ? "descending" : undefined
                }
                className={`rotulo border-b border-border px-3 py-2.5 whitespace-nowrap ${
                  numero ? "text-right" : "text-left"
                }`}
              >
                {puedeOrdenar ? (
                  <button
                    type="button"
                    onClick={header.column.getToggleSortingHandler()}
                    className={`inline-flex items-center gap-1 rounded-sm transition-colors hover:text-foreground ${
                      orden ? "text-foreground" : ""
                    }`}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    <IconoOrden orden={orden} />
                  </button>
                ) : (
                  flexRender(header.column.columnDef.header, header.getContext())
                )}
              </th>
            );
          })}
        </tr>
      ))}
    </thead>
  );
}

/** El estado del orden era `" ↑"` concatenado al texto: una flecha suelta que
 * ni se alinea ni se lee como control. La tercera cara —"esta columna se
 * puede ordenar y no lo está"— no existía. */
function IconoOrden({ orden }: { orden: false | "asc" | "desc" }) {
  if (orden === "asc") return <ChevronUp size={13} strokeWidth={2.5} aria-hidden />;
  if (orden === "desc") return <ChevronDown size={13} strokeWidth={2.5} aria-hidden />;
  return <ChevronsUpDown size={13} strokeWidth={2} aria-hidden className="opacity-40" />;
}
