"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  ETIQUETA_ESTADO_ENTREGA,
  ETIQUETA_MOTIVO,
  type EntregaHistorial,
  type MotivoFallo,
} from "@/lib/delivery";

function hora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-PE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function EvidenciaDialogo({ entregaId }: { entregaId: string }) {
  const [abierto, setAbierto] = useState(false);
  const [sinFoto, setSinFoto] = useState(false);

  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => setAbierto(true)}>
        Ver foto
      </Button>
      <Dialog
        open={abierto}
        onOpenChange={(v) => {
          setAbierto(v);
          if (v) setSinFoto(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Evidencia de la entrega</DialogTitle>
          </DialogHeader>
          {sinFoto ? (
            <p className="text-sm text-gray">Esta entrega no tiene foto de evidencia.</p>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/api/proxy/api/v1/delivery/entregas/${entregaId}/evidencia`}
              alt="Evidencia de la entrega"
              className="w-full rounded-lg"
              onError={() => setSinFoto(true)}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function Fila({ entrega }: { entrega: EntregaHistorial }) {
  return (
    <tr className="border-b border-border">
      <td className="px-3 py-2">{entrega.numero_orden ?? "—"}</td>
      <td className="px-3 py-2">{entrega.direccion_entrega ?? "—"}</td>
      <td className="px-3 py-2">{entrega.cliente_nombre ?? "—"}</td>
      <td className="px-3 py-2">{entrega.repartidor_nombre ?? "—"}</td>
      <td className="px-3 py-2">
        <Badge variant="outline">{ETIQUETA_ESTADO_ENTREGA[entrega.estado] ?? entrega.estado}</Badge>
      </td>
      <td className="px-3 py-2">{entrega.intentos}</td>
      <td className="px-3 py-2">{hora(entrega.fecha_entrega)}</td>
      <td className="px-3 py-2">
        {entrega.motivo_fallo
          ? ETIQUETA_MOTIVO[entrega.motivo_fallo as MotivoFallo]
          : (entrega.observacion ?? "—")}
      </td>
      <td className="px-3 py-2">
        {entrega.estado === "entregada" || entrega.estado === "fallida" ? (
          <EvidenciaDialogo entregaId={entrega.id} />
        ) : null}
      </td>
    </tr>
  );
}

export default function EntregasCliente({ items }: { items: EntregaHistorial[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray">No hay entregas para estos filtros.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-card text-gray">
          <tr>
            <th className="px-3 py-2 font-medium">Pedido</th>
            <th className="px-3 py-2 font-medium">Dirección</th>
            <th className="px-3 py-2 font-medium">Cliente</th>
            <th className="px-3 py-2 font-medium">Repartidor</th>
            <th className="px-3 py-2 font-medium">Estado</th>
            <th className="px-3 py-2 font-medium">Intentos</th>
            <th className="px-3 py-2 font-medium">Fecha</th>
            <th className="px-3 py-2 font-medium">Motivo / Nota</th>
            <th className="px-3 py-2 font-medium">Evidencia</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => (
            <Fila key={e.id} entrega={e} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
