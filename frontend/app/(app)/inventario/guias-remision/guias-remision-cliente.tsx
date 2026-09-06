"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

export type GuiaRemision = {
  id: string;
  transferencia_id: string | null;
  devolucion_id: string | null;
  serie: string;
  correlativo: number;
  fecha_inicio_traslado: string;
  lugar_origen: string;
  lugar_destino: string;
  chofer_nombres: string;
  chofer_apellidos: string;
  vehiculo_placa: string;
  estado_emision: string;
  detalle_emision: string | null;
};

const TONO: Record<string, "exito" | "alerta" | "peligro" | "info" | "neutro"> = {
  pendiente: "info",
  aceptado: "exito",
  rechazado: "peligro",
  error: "alerta",
};

/**
 * Guías de remisión ya emitidas: qué salió del almacén por la vía pública.
 *
 * Solo lectura — la guía se emite desde la ficha del traslado o de la
 * devolución a proveedor, que es donde vive el documento que la sustenta
 * (RN-TRP-002). Esta pantalla es para revisar lo ya emitido y, sobre todo,
 * para encontrar rápido lo `rechazado`: una guía que SUNAT no aceptó hay
 * que corregirla y reemitirla desde su origen.
 */
export function GuiasRemisionCliente({ guias }: { guias: GuiaRemision[] }) {
  const columnas = useMemo<ColumnDef<GuiaRemision>[]>(
    () => [
      {
        header: "Guía",
        accessorFn: (g) => `${g.serie}-${String(g.correlativo).padStart(8, "0")}`,
      },
      {
        header: "Origen",
        accessorFn: (g) => (g.transferencia_id ? "Traslado" : "Devolución a proveedor"),
      },
      { header: "De", accessorKey: "lugar_origen" },
      { header: "A", accessorKey: "lugar_destino" },
      {
        header: "Chofer",
        accessorFn: (g) => `${g.chofer_nombres} ${g.chofer_apellidos}`,
      },
      { header: "Placa", accessorKey: "vehiculo_placa" },
      {
        header: "Estado",
        accessorKey: "estado_emision",
        cell: ({ row }) => (
          <Insignia tono={TONO[row.original.estado_emision] ?? "neutro"}>
            {row.original.estado_emision}
          </Insignia>
        ),
      },
      {
        id: "descarga",
        header: "",
        cell: ({ row }) =>
          row.original.estado_emision !== "aceptado" ? null : (
            <div className="flex gap-3">
              {(["pdf", "xml", "cdr"] as const).map((formato) => (
                <a
                  key={formato}
                  href={`/api/proxy/api/v1/inventory/guias-remision/${row.original.id}/descargar/${formato}`}
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  {formato.toUpperCase()}
                </a>
              ))}
            </div>
          ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Guías de remisión
        </h1>
        <p className="text-xs text-gray">
          Lo que salió del almacén con guía. Se emite desde el traslado o la
          devolución a proveedor — acá se revisa lo ya emitido.
        </p>
      </div>

      <TablaDatos
        columnas={columnas}
        datos={guias}
        placeholderBusqueda="Buscar por chofer, placa o lugar..."
        vacio="Todavía no se emitió ninguna guía."
      />
    </div>
  );
}
