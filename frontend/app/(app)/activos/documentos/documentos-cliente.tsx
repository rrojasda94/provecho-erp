"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { adjuntarArchivoAction, crearDocumentoAction, renovarDocumentoAction } from "./actions";

export type Documento = {
  id: string;
  sujeto_tipo: string;
  sujeto_id: string;
  tipo_documento: string;
  numero: string | null;
  fecha_vencimiento: string;
  estado: string | null;
  renovado_por_id: string | null;
};

const TIPOS_DOCUMENTO = [
  ["soat", "SOAT"],
  ["revision_tecnica", "Revisión técnica"],
  ["tarjeta_propiedad", "Tarjeta de propiedad"],
  ["poliza_seguro", "Póliza de seguro"],
  ["garantia", "Garantía"],
  ["licencia_funcionamiento", "Licencia de funcionamiento"],
  ["certificado_defensa_civil", "Certificado de Defensa Civil"],
  ["fumigacion", "Fumigación"],
  ["registro_sanitario", "Registro sanitario"],
  ["carne_sanidad", "Carné de sanidad"],
  ["licencia_conducir", "Licencia de conducir"],
  ["otro", "Otro"],
] as const;

function EstadoDerivadoInsignia({ estado }: { estado: string | null }) {
  if (estado === "vencido") return <Insignia tono="peligro">Vencido</Insignia>;
  if (estado === "proximo") return <Insignia tono="alerta">Próximo</Insignia>;
  if (estado === "renovado") return <Insignia tono="neutro">Renovado</Insignia>;
  return <Insignia tono="exito">Al día</Insignia>;
}

function DialogoNuevoDocumento({ nombreActivo }: { nombreActivo: Map<string, string> }) {
  return (
    <DialogoFormulario
      titulo="Nuevo documento con vencimiento"
      disparador="+ Nuevo documento"
      accion={crearDocumentoAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Sujeto
        <select name="sujeto_tipo" defaultValue="activo">
          <option value="activo">Activo</option>
          <option value="sucursal">Sucursal</option>
          <option value="empresa">Empresa</option>
          <option value="trabajador">Trabajador</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ID del sujeto
        <input name="sujeto_id" required placeholder="UUID del activo/sucursal/empresa/trabajador" />
      </label>
      {nombreActivo.size > 0 && (
        <p className="text-xs text-muted-foreground">
          Activos: {[...nombreActivo.entries()].map(([id, n]) => `${n} (${id})`).join(" · ")}
        </p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo de documento
        <select name="tipo_documento" required defaultValue="">
          <option value="" disabled>
            Elegir…
          </option>
          {TIPOS_DOCUMENTO.map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Número
        <input name="numero" maxLength={60} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Emisor
        <input name="emisor" maxLength={120} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de vencimiento
        <input name="fecha_vencimiento" type="date" required />
      </label>
    </DialogoFormulario>
  );
}

export function DocumentosCliente({
  documentos,
  nombreActivo,
}: {
  documentos: Documento[];
  nombreActivo: Map<string, string>;
}) {
  const columnas: ColumnDef<Documento>[] = useMemo(
    () => [
      {
        id: "tipo",
        header: "Tipo",
        accessorFn: (d) => TIPOS_DOCUMENTO.find(([v]) => v === d.tipo_documento)?.[1] ?? d.tipo_documento,
      },
      {
        id: "sujeto",
        header: "Sujeto",
        accessorFn: (d) =>
          d.sujeto_tipo === "activo"
            ? (nombreActivo.get(d.sujeto_id) ?? `activo ${d.sujeto_id}`)
            : `${d.sujeto_tipo}`,
      },
      { accessorKey: "numero", header: "Número", cell: ({ getValue }) => getValue<string>() ?? "—" },
      { accessorKey: "fecha_vencimiento", header: "Vence" },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => <EstadoDerivadoInsignia estado={getValue<string>()} />,
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => {
          const d = row.original;
          if (d.renovado_por_id) return null;
          return (
            <div className="flex items-center gap-2">
              <DialogoFormulario
                titulo="Renovar documento"
                disparador="Renovar"
                claseDisparador="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                accion={renovarDocumentoAction}
              >
                <input type="hidden" name="documento_id" value={d.id} />
                <label className="flex flex-col gap-1 text-sm font-semibold">
                  Número nuevo (opcional)
                  <input name="numero" maxLength={60} />
                </label>
                <label className="flex flex-col gap-1 text-sm font-semibold">
                  Nueva fecha de vencimiento
                  <input name="fecha_vencimiento" type="date" required />
                </label>
              </DialogoFormulario>
              <DialogoFormulario
                titulo="Adjuntar archivo"
                disparador="Adjuntar"
                claseDisparador="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                accion={adjuntarArchivoAction}
              >
                <input type="hidden" name="documento_id" value={d.id} />
                <label className="flex flex-col gap-1 text-sm font-semibold">
                  Archivo (PDF o imagen, máx. 20 MB)
                  <input name="archivo" type="file" accept="application/pdf,image/*" required />
                </label>
              </DialogoFormulario>
              {d.sujeto_tipo === "activo" && (
                <Link href={`/activos/activos/${d.sujeto_id}`} className="text-xs font-medium underline">
                  Ver activo
                </Link>
              )}
            </div>
          );
        },
      },
    ],
    [nombreActivo],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Documentos con vencimiento</h1>
        <DialogoNuevoDocumento nombreActivo={nombreActivo} />
      </div>
      <TablaDatos columnas={columnas} datos={documentos} placeholderBusqueda="Buscar documento..." />
    </div>
  );
}
