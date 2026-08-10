"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { primeroElDe } from "@/lib/destinos";

export type Categoria = {
  id: string;
  empresa_id: string;
  nombre: string;
  frecuencia_conteo: string | null;
};

export type ProgramaConteo = {
  almacen_id: string;
  categoria_id: string;
  categoria: string;
  frecuencia: string;
  ultimo_conteo: string | null;
  proxima_fecha: string;
  estado: string;
  dias_atraso: number;
};

type Fila = Categoria & { estado: string; proxima: string; atraso: number };

/** Destino de `inventory.conteo_vencido` (ADR-036): el reporte dice que una
 * categoría se pasó de su fecha; acá se ve cuánto y cuál es su frecuencia. */
export function CategoriasCliente({
  categorias,
  programa,
  resaltado,
}: {
  categorias: Categoria[];
  programa: ProgramaConteo[];
  resaltado: string | null;
}) {
  const filas = useMemo<Fila[]>(() => {
    // Una categoría puede estar programada en varios almacenes: manda la más
    // atrasada, que es la que hay que ir a contar.
    const peor = new Map<string, ProgramaConteo>();
    for (const p of programa) {
      const actual = peor.get(p.categoria_id);
      if (!actual || p.dias_atraso > actual.dias_atraso) peor.set(p.categoria_id, p);
    }
    const lista = categorias.map((c) => {
      const p = peor.get(c.id);
      return {
        ...c,
        estado: p?.estado ?? "sin programa",
        proxima: p?.proxima_fecha ?? "—",
        atraso: p?.dias_atraso ?? 0,
      };
    });
    return primeroElDe(lista, resaltado, (c) => c.id);
  }, [categorias, programa, resaltado]);

  const columnas = useMemo<ColumnDef<Fila>[]>(
    () => [
      { header: "Categoría", accessorKey: "nombre" },
      {
        header: "Frecuencia",
        accessorKey: "frecuencia_conteo",
        cell: ({ row }) => row.original.frecuencia_conteo ?? "Fuera del conteo cíclico",
      },
      { header: "Próximo conteo", accessorKey: "proxima" },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) =>
          row.original.estado === "vencido" ? (
            <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
              Vencido · {row.original.atraso} día(s)
            </span>
          ) : (
            <span className="text-sm text-gray">{row.original.estado}</span>
          ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Categorías</h1>
      <TablaDatos
        columnas={columnas}
        datos={filas}
        placeholderBusqueda="Buscar categoría..."
      />
    </div>
  );
}
