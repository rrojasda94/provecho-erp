"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import type { Proveedor } from "../ordenes-compra/ordenes-compra-cliente";

export type ComprobanteRecibido = {
  id: string;
  compra_id: string | null;
  proveedor_id: string | null;
  proveedor: string | null;
  emisor_num_doc: string | null;
  tipo: string;
  serie: string;
  correlativo: number;
  fecha_emision: string | null;
  total: string | null;
  total_orden: string | null;
  sustento: string;
  gravado_igv: boolean | null;
  created_at: string;
};

const ETIQUETA_TIPO: Record<string, string> = {
  factura: "Factura",
  boleta: "Boleta",
  rhe: "RHE",
  ticket_compra: "Ticket",
};

function soles(valor: string | null): string {
  return valor === null ? "—" : `S/ ${Number(valor).toFixed(2)}`;
}

export function FacturasCliente({
  facturas,
  total,
  recortado,
  proveedores,
  filtros,
}: {
  facturas: ComprobanteRecibido[];
  total: number;
  recortado: boolean;
  proveedores: Proveedor[];
  filtros: { proveedor: string; desde: string; hasta: string };
}) {
  const router = useRouter();
  const params = useSearchParams();

  const filtrar = (campo: string, valor: string) => {
    const nuevos = new URLSearchParams(params.toString());
    if (valor) nuevos.set(campo, valor);
    else nuevos.delete(campo);
    router.push(`/compras/facturas?${nuevos}`);
  };

  const columnas = useMemo<ColumnDef<ComprobanteRecibido>[]>(
    () => [
      {
        id: "documento",
        header: "Documento",
        accessorFn: (c) => `${ETIQUETA_TIPO[c.tipo] ?? c.tipo} ${c.serie}-${c.correlativo}`,
        cell: ({ row }) =>
          row.original.compra_id ? (
            <Link
              href={`/compras/ordenes-compra/${row.original.compra_id}`}
              className="font-semibold text-primary hover:underline"
            >
              {ETIQUETA_TIPO[row.original.tipo] ?? row.original.tipo}{" "}
              {row.original.serie}-{row.original.correlativo}
            </Link>
          ) : (
            <span className="font-semibold">
              {row.original.serie}-{row.original.correlativo}
            </span>
          ),
      },
      {
        header: "Proveedor",
        accessorFn: (c) => c.proveedor ?? c.emisor_num_doc ?? "—",
      },
      { header: "RUC", accessorFn: (c) => c.emisor_num_doc ?? "—" },
      {
        header: "Emitida",
        accessorFn: (c) => c.fecha_emision ?? "—",
      },
      {
        header: "Total del papel",
        accessorFn: (c) => (c.total === null ? -1 : Number(c.total)),
        cell: ({ row }) => <span className="cifra">{soles(row.original.total)}</span>,
      },
      {
        header: "Total de la OC",
        accessorFn: (c) => (c.total_orden === null ? -1 : Number(c.total_orden)),
        cell: ({ row }) => (
          <span className="cifra text-gray">{soles(row.original.total_orden)}</span>
        ),
      },
      {
        header: "IGV",
        accessorFn: (c) =>
          c.gravado_igv === null ? "Según empresa" : c.gravado_igv ? "Gravada" : "Exonerada",
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Facturas de proveedor
        </h1>
        <p className="text-xs text-gray">
          Lo que la empresa recibió. <strong>Total del papel</strong> es lo que
          declara el proveedor y <strong>total de la OC</strong> lo que se
          recibió sin IGV: son números distintos por definición, y la
          diferencia es lo que hay que conciliar.
        </p>
      </header>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Proveedor
          <Combobox
            etiqueta="Proveedor"
            marcador="Todos"
            value={filtros.proveedor}
            alCambiar={(v) => filtrar("proveedor", v ?? "")}
            opciones={proveedores.map((p) => ({
              valor: p.id,
              etiqueta: p.razon_social ?? p.ruc ?? "",
            }))}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Desde
          <input
            type="date"
            value={filtros.desde}
            onChange={(e) => filtrar("desde", e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Hasta
          <input
            type="date"
            value={filtros.hasta}
            onChange={(e) => filtrar("hasta", e.target.value)}
          />
        </label>
      </div>

      {recortado && (
        <p className="rounded-lg bg-status-warning-surface px-3 py-2 text-sm text-status-warning">
          Se muestran {facturas.length} de {total}. Acota por proveedor o por
          fecha para ver el resto.
        </p>
      )}

      <TablaDatos
        columnas={columnas}
        datos={facturas}
        placeholderBusqueda="Buscar por documento, proveedor o RUC..."
        vacio="No hay facturas de proveedor con esos filtros."
      />
      <p className="text-xs text-gray">
        Lo registrado antes de agosto de 2026 no tiene fecha ni total del papel:
        esas columnas no existían y no se inventaron al migrar.
      </p>
    </div>
  );
}
