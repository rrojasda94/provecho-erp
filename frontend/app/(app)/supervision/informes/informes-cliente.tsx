"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { generarInformeAction } from "./actions";

export type InformeDiario = {
  id: string;
  sucursal_id: string;
  fecha: string;
  total: number;
  completadas: number;
  vencidas: number;
  fotos_invalidas: number;
};
export type Sucursal = { id: string; nombre: string };

function hoyISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function GenerarInforme({ sucursales }: { sucursales: Sucursal[] }) {
  const router = useRouter();
  const [sucursalId, setSucursalId] = useState(sucursales[0]?.id ?? "");
  const [fecha, setFecha] = useState(hoyISO());
  const [pendiente, iniciarTransicion] = useTransition();
  const [aviso, setAviso] = useState("");

  if (sucursales.length === 0) return null;

  function generar() {
    setAviso("");
    iniciarTransicion(async () => {
      const r = await generarInformeAction(sucursalId, fecha);
      setAviso(r.ok ? "Informe generado." : r.error);
      router.refresh();
    });
  }

  return (
    <div className="flex items-center gap-2">
      <select value={sucursalId} onChange={(e) => setSucursalId(e.target.value)}>
        {sucursales.map((s) => (
          <option key={s.id} value={s.id}>
            {s.nombre}
          </option>
        ))}
      </select>
      <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
      <button
        type="button"
        onClick={generar}
        disabled={pendiente}
        className="inline-flex items-center justify-center rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground hover:bg-primary/85 disabled:opacity-50"
      >
        {pendiente ? "Generando..." : "Generar informe"}
      </button>
      {aviso && <span className="text-sm text-gray">{aviso}</span>}
    </div>
  );
}

/** Un informe por sucursal por día, generado al cerrar la jornada. Se
 * escala desde el módulo Reportes (ADR-036), no desde acá. */
export function InformesCliente({
  informes,
  sucursales,
}: {
  informes: InformeDiario[];
  sucursales: Sucursal[];
}) {
  const columnas: ColumnDef<InformeDiario>[] = [
    { accessorKey: "fecha", header: "Fecha" },
    { accessorKey: "total", header: "Total", meta: { numero: true } },
    { accessorKey: "completadas", header: "Completadas", meta: { numero: true } },
    { accessorKey: "vencidas", header: "Vencidas", meta: { numero: true } },
    { accessorKey: "fotos_invalidas", header: "Fotos a revisar", meta: { numero: true } },
    {
      id: "ver",
      header: "",
      cell: ({ row }) => (
        <Link
          href={`/supervision/informes/${row.original.id}`}
          className="text-sm font-semibold text-primary hover:underline"
        >
          Ver
        </Link>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="font-heading text-xl text-dark">Informes de supervisión</h1>
        <GenerarInforme sucursales={sucursales} />
      </div>
      <TablaDatos columnas={columnas} datos={informes} placeholderBusqueda="Buscar..." />
    </div>
  );
}
