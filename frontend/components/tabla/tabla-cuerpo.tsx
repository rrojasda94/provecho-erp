"use client";

import type { Table } from "@tanstack/react-table";
import { flexRender } from "@tanstack/react-table";

import { Skeleton } from "@/components/ui/skeleton";

/**
 * Cuerpo de la tabla, con sus tres estados posibles: cargando, sin filas y
 * con filas. Separado de `tabla-datos.tsx` por el límite de complejidad.
 *
 * El vacío se dibuja fuera de la tabla (lo compone el llamador): meter un
 * bloque con ícono y botón dentro de un `<td colSpan>` obliga a que el ancho
 * del vacío dependa de cuántas columnas tenga la tabla, que es exactamente lo
 * que no debería importarle.
 */
export function TablaCuerpo<T>({
  tabla,
  cargando,
  columnas,
  denso,
}: {
  tabla: Table<T>;
  cargando: boolean;
  columnas: number;
  denso: boolean;
}) {
  const alto = denso ? "py-1.5" : "py-2.5";

  if (cargando) {
    return (
      <tbody aria-busy>
        {Array.from({ length: 5 }, (_, fila) => (
          <tr key={fila} className="border-t border-border">
            {Array.from({ length: columnas }, (_, celda) => (
              <td key={celda} className={`px-3 ${alto}`}>
                {/* Anchos desparejos y no todos iguales: una grilla de
                    rectángulos idénticos se lee como una tabla rota, no como
                    una tabla cargando. */}
                <Skeleton className={`h-4 ${celda % 3 === 0 ? "w-3/5" : "w-4/5"}`} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    );
  }

  return (
    <tbody>
      {tabla.getRowModel().rows.map((fila) => (
        <tr
          key={fila.id}
          className="border-t border-border transition-colors hover:bg-muted/50 focus-within:bg-muted/50"
        >
          {fila.getVisibleCells().map((celda) => (
            <td
              key={celda.id}
              className={`px-3 ${alto} ${
                celda.column.columnDef.meta?.numero ? "cifra text-right" : ""
              }`}
            >
              {flexRender(celda.column.columnDef.cell, celda.getContext())}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}
