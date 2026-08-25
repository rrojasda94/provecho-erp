"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Printer } from "lucide-react";
import { useMemo, useState } from "react";

import { Insignia } from "@/components/estado/insignia";
import { HojaImpresion, useImpresion } from "@/components/impresion/hoja";
import { TicketDeComprobante } from "@/components/impresion/ticket-comprobante";
import type { TicketComprobante } from "@/components/impresion/tipos";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { pedir } from "@/lib/cliente-api";

export type ComprobanteEmitido = {
  id: string;
  venta_id: string | null;
  tipo: string;
  serie: string;
  correlativo: number;
  serie_correlativo: string;
  grupo_cobro: number;
  fecha_emision: string;
  receptor_num_doc: string | null;
  receptor_nombre: string | null;
  estado_emision: string;
  detalle_emision: string | null;
  total: string;
  anulado_por_nc_id: string | null;
};

const ETIQUETA_TIPO: Record<string, string> = {
  boleta: "Boleta",
  factura: "Factura",
  nc: "Nota de crédito",
};

/** `aceptado` es lo normal, `rechazado` es el único que exige que alguien
 * haga algo, y `pendiente`/`error` son "todavía en camino": tres tonos, no
 * cuatro colores distintos que obliguen a recordar cuál era cuál. */
function tonoDe(estado: string) {
  if (estado === "aceptado") return "exito" as const;
  if (estado === "rechazado") return "peligro" as const;
  return "alerta" as const;
}

const fecha = (iso: string) =>
  new Date(iso).toLocaleString("es-PE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export function ComprobantesCliente({
  comprobantes,
  total,
  desde,
  hasta,
}: {
  comprobantes: ComprobanteEmitido[];
  total: number;
  desde: string | null;
  hasta: string | null;
}) {
  const [ticket, setTicket] = useState<TicketComprobante | null>(null);
  const [imprimiendoId, setImprimiendoId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const { imprimir } = useImpresion();

  const reimprimir = async (comprobante: ComprobanteEmitido) => {
    setImprimiendoId(comprobante.id);
    setError("");
    try {
      setTicket(
        await pedir<TicketComprobante>(
          `/sales/comprobantes/${comprobante.id}/ticket`,
        ),
      );
      imprimir();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "No se pudo preparar el comprobante",
      );
    } finally {
      setImprimiendoId(null);
    }
  };

  const columnas: ColumnDef<ComprobanteEmitido>[] = useMemo(
    () => [
      {
        accessorKey: "serie_correlativo",
        header: "Documento",
        cell: ({ row }) => (
          <span className="font-semibold">
            {ETIQUETA_TIPO[row.original.tipo] ?? row.original.tipo}{" "}
            {row.original.serie_correlativo}
          </span>
        ),
      },
      {
        id: "fecha",
        header: "Emitido",
        accessorFn: (c) => fecha(c.fecha_emision),
      },
      {
        id: "receptor",
        header: "Cliente",
        // Sin receptor tecleado la boleta salió a "clientes varios"
        // (RN-PER-005): decirlo es más honesto que dejar la celda vacía.
        accessorFn: (c) => c.receptor_nombre ?? "Clientes varios",
      },
      {
        id: "documento_receptor",
        header: "DNI / RUC",
        accessorFn: (c) => c.receptor_num_doc ?? "—",
      },
      {
        id: "total",
        header: "Total",
        accessorFn: (c) => `S/ ${c.total}`,
      },
      {
        accessorKey: "estado_emision",
        header: "SUNAT",
        cell: ({ row }) => (
          <span title={row.original.detalle_emision ?? undefined}>
            <Insignia tono={tonoDe(row.original.estado_emision)}>
              {row.original.estado_emision}
            </Insignia>
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={imprimiendoId !== null || row.original.tipo === "nc"}
              onClick={() => reimprimir(row.original)}
              // La nota de crédito todavía no tiene representación impresa
              // propia: el ticket se arma con las líneas acreditadas y no
              // con las del comprobante (ver Deuda técnica).
              title={
                row.original.tipo === "nc"
                  ? "La nota de crédito todavía se entrega en PDF"
                  : "Imprimir en la ticketera de 80 mm"
              }
              className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:underline disabled:text-gray disabled:no-underline"
            >
              <Printer size={14} aria-hidden />
              {imprimiendoId === row.original.id ? "Preparando…" : "Imprimir"}
            </button>
            <a
              href={`/api/proxy/api/v1/sales/comprobantes/${row.original.id}/descargar/pdf`}
              className="text-xs font-semibold hover:underline"
            >
              PDF
            </a>
            <a
              href={`/api/proxy/api/v1/sales/comprobantes/${row.original.id}/descargar/xml`}
              className="text-xs font-semibold hover:underline"
            >
              XML
            </a>
          </div>
        ),
      },
    ],
    [imprimiendoId],
  );

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="font-heading text-xl">Comprobantes emitidos</h1>
        <p className="text-sm text-gray">
          {desde || hasta
            ? `${desde ?? "…"} → ${hasta ?? desde ?? "…"}`
            : "Hoy"}{" "}
          · {total} {total === 1 ? "documento" : "documentos"}
        </p>
      </header>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      <TablaDatos
        columnas={columnas}
        datos={comprobantes}
        placeholderBusqueda="Buscar por serie, cliente o documento..."
        denso
        vacio={<p>No se emitió ningún comprobante en el rango elegido.</p>}
      />

      {ticket && (
        <HojaImpresion>
          <TicketDeComprobante ticket={ticket} />
        </HojaImpresion>
      )}
    </section>
  );
}
