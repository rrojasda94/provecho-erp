"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { AvisoRecortado } from "@/components/estado/aviso-recortado";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import { generarReporteJornadaAction, visarReporteJornadaAction } from "./actions";

import type { Almacen } from "../ordenes-cliente";

export type ReporteJornada = {
  id: string;
  almacen_id: string;
  jornada: string;
  generado_at: string;
  ordenes: unknown[];
  merma_total: string;
  desperdicio_total: string;
  horas_hombre_total: string;
  costo_total: string;
  visado_por: string | null;
  visado_at: string | null;
  observaciones: string | null;
};

function DialogoGenerarReporte({ almacenes }: { almacenes: Almacen[] }) {
  return (
    <DialogoFormulario
      titulo="Generar reporte de jornada"
      disparador="+ Generar"
      etiquetaEnvio="Generar"
      etiquetaPendiente="Generando..."
      accion={generarReporteJornadaAction}
      ayuda="El barrido de cierre ya lo genera solo pasada la hora de cierre de la empresa (RN-DOC-010); esto es para adelantarlo o volver a calcularlo antes de visar."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir almacén..."
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Jornada
        <input name="fecha" type="date" />
        <span className="text-xs font-normal text-muted-foreground">
          Vacío = hoy.
        </span>
      </label>
    </DialogoFormulario>
  );
}

function DialogoVisar({ reporte }: { reporte: ReporteJornada }) {
  return (
    <DialogoFormulario
      titulo="Visar reporte de jornada"
      disparador="Visar"
      claseDisparador="text-xs font-bold text-primary hover:underline"
      etiquetaEnvio="Visar"
      etiquetaPendiente="Visando..."
      accion={visarReporteJornadaAction}
      ayuda="Se visa lo que la jornada ya generó, no se redacta contenido nuevo (RN-DOC-010)."
    >
      <input type="hidden" name="reporte_id" value={reporte.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Observaciones
        <textarea name="observaciones" rows={3} maxLength={1000} placeholder="Opcional" />
      </label>
    </DialogoFormulario>
  );
}

export function ReportesCliente({
  reportes,
  total,
  almacenes,
}: {
  reportes: ReporteJornada[];
  /** Cuántos hay en total: la página viene recortada. */
  total: number;
  almacenes: Almacen[];
}) {
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );

  const columnas: ColumnDef<ReporteJornada>[] = useMemo(
    () => [
      { id: "jornada", header: "Jornada", accessorKey: "jornada" },
      {
        id: "almacen",
        header: "Almacén",
        accessorFn: (r) => nombreAlmacen.get(r.almacen_id) ?? "—",
      },
      { id: "ordenes", header: "Órdenes", accessorFn: (r) => r.ordenes.length },
      { id: "merma", header: "Merma", accessorKey: "merma_total" },
      { id: "desperdicio", header: "Desperdicio", accessorKey: "desperdicio_total" },
      { id: "horas", header: "Horas-hombre", accessorKey: "horas_hombre_total" },
      { id: "costo", header: "Costo total", accessorKey: "costo_total" },
      {
        id: "estado",
        header: "Estado",
        cell: ({ row }) => {
          const r = row.original;
          const clase = r.visado_at
            ? "bg-accent/30 text-dark"
            : "bg-primary/15 text-primary";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {r.visado_at ? "Visado" : "Pendiente de visado"}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (row.original.visado_at ? null : <DialogoVisar reporte={row.original} />),
      },
    ],
    [nombreAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Reportes de producción</h1>
        <DialogoGenerarReporte almacenes={almacenes} />
      </div>
      <p className="text-sm text-gray">
        Se consolida solo con lo que la cocina fue registrando durante el día — el jefe de
        cocina visa, no redacta (RN-DOC-010). El barrido de cierre lo genera solo pasada la
        hora de cierre de cada empresa.
      </p>
      <AvisoRecortado
        mostrados={reportes.length}
        total={total}
        sugerencia="Acota por almacén o jornada para ver el resto."
      />
      <TablaDatos columnas={columnas} datos={reportes} placeholderBusqueda="Buscar reporte..." />
    </div>
  );
}
