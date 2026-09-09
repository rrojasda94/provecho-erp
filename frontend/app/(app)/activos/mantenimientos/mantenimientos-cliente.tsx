"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

export type OrdenMantenimiento = {
  id: string;
  activo_id: string;
  tipo: string;
  estado: string;
  fecha_programada: string | null;
  fecha_realizada: string | null;
  descripcion: string | null;
};

function EstadoOrdenInsignia({ estado }: { estado: string }) {
  if (estado === "realizada") return <Insignia tono="exito">Realizada</Insignia>;
  if (estado === "cancelada") return <Insignia tono="neutro">Cancelada</Insignia>;
  if (estado === "en_curso") return <Insignia tono="alerta">En curso</Insignia>;
  return <Insignia tono="info">Programada</Insignia>;
}

export function MantenimientosCliente({
  ordenes,
  nombreActivo,
}: {
  ordenes: OrdenMantenimiento[];
  nombreActivo: Map<string, string>;
}) {
  const columnas: ColumnDef<OrdenMantenimiento>[] = useMemo(
    () => [
      {
        id: "activo",
        header: "Activo",
        accessorFn: (o) => nombreActivo.get(o.activo_id) ?? o.activo_id,
      },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "descripcion",
        header: "Descripción",
        accessorFn: (o) => o.descripcion ?? "—",
      },
      {
        id: "fecha",
        header: "Fecha",
        accessorFn: (o) => o.fecha_realizada ?? o.fecha_programada ?? "—",
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => <EstadoOrdenInsignia estado={getValue<string>()} />,
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <Link
            href={`/activos/activos/${row.original.activo_id}`}
            className="text-xs font-medium underline"
          >
            Ver activo
          </Link>
        ),
      },
    ],
    [nombreActivo],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Mantenimientos</h1>
      <TablaDatos
        columnas={columnas}
        datos={ordenes}
        placeholderBusqueda="Buscar mantenimiento..."
      />
    </div>
  );
}
