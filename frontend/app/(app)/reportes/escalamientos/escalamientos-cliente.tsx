"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import {
  ETIQUETA_ESTADO,
  ETIQUETA_MOTIVO,
  ETIQUETA_NIVEL,
  terminado,
  type Escalamiento,
} from "@/lib/reports";

/**
 * La bandeja del que responde: qué está abierto y en qué nivel (ADR-036).
 *
 * Los filtros viven en la URL, no en estado del cliente: «lo que le toca a
 * Comercial hoy» es una dirección que se comparte y se recarga — mismo
 * criterio que la jornada de ventas.
 */
export function EscalamientosCliente({
  escalamientos,
  nivel,
  estado,
}: {
  escalamientos: Escalamiento[];
  nivel: string;
  estado: string;
}) {
  const router = useRouter();

  function filtrar(clave: "nivel" | "estado", valor: string) {
    const query = new URLSearchParams({ nivel, estado });
    query.set(clave, valor);
    for (const [k, v] of [...query]) if (!v) query.delete(k);
    router.push(`/reportes/escalamientos?${query}`);
  }

  const columnas = useMemo<ColumnDef<Escalamiento>[]>(
    () => [
      {
        header: "Nivel",
        accessorKey: "nivel_actual",
        cell: ({ row }) => (
          <span
            className={`rounded px-2 py-0.5 text-xs font-bold ${
              terminado(row.original.estado)
                ? "bg-gray/15 text-secondary"
                : "bg-amber-100 text-amber-900"
            }`}
          >
            {ETIQUETA_NIVEL[row.original.nivel_actual] ?? row.original.nivel_actual}
          </span>
        ),
      },
      {
        header: "Motivo",
        accessorKey: "motivo",
        cell: ({ row }) => (
          <Link
            href={`/reportes/escalamientos/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {ETIQUETA_MOTIVO[row.original.motivo] ?? row.original.motivo}
          </Link>
        ),
      },
      { header: "Qué pasó", accessorKey: "descripcion" },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => ETIQUETA_ESTADO[row.original.estado] ?? row.original.estado,
      },
      {
        header: "Abierto",
        accessorKey: "created_at",
        cell: ({ row }) => new Date(row.original.created_at).toLocaleString("es-PE"),
      },
    ],
    [],
  );

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Escalamientos</h1>
          <p className="text-sm text-secondary">
            Lo que se elevó porque no se pudo resolver donde llegó.
          </p>
        </div>
        <div className="flex gap-3">
          <label className="flex items-center gap-2 text-sm font-semibold">
            Nivel
            <select value={nivel} onChange={(e) => filtrar("nivel", e.target.value)}>
              <option value="">Todos</option>
              <option value="supervisor">Supervisor</option>
              <option value="comercial">Comercial</option>
              <option value="gerencia">Gerencia</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold">
            Estado
            <select value={estado} onChange={(e) => filtrar("estado", e.target.value)}>
              <option value="">Todos</option>
              <option value="abierto">Abierto</option>
              <option value="escalado">Escalado</option>
              <option value="resuelto_supervisor">Resuelto por supervisor</option>
              <option value="resuelto">Resuelto</option>
            </select>
          </label>
        </div>
      </header>
      <TablaDatos
        columnas={columnas}
        datos={escalamientos}
        placeholderBusqueda="Buscar por motivo o descripción..."
      />
    </section>
  );
}
