"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorApi } from "@/lib/cliente-api";
import { apiDelivery, ETIQUETA_VEHICULO, type Repartidor, type VentaLista } from "@/lib/delivery";

type Props = {
  sucursalId: string;
  sinAsignar: VentaLista[];
  repartidores: Repartidor[];
  onCreada: () => void;
};

function etiquetaRepartidor(r: Repartidor): string {
  const vehiculo = ETIQUETA_VEHICULO[r.vehiculo_tipo];
  return r.nombre ? `${r.nombre} (${vehiculo})` : vehiculo;
}

function etiquetaVenta(v: VentaLista): string {
  const km = v.distancia_entrega_km ? ` · ${v.distancia_entrega_km} km` : "";
  return `#${v.numero_orden} · ${v.direccion_entrega ?? "Sin dirección"}${km}`;
}

export default function NuevaRutaDialogo({
  sucursalId,
  sinAsignar,
  repartidores,
  onCreada,
}: Props) {
  const [abierto, setAbierto] = useState(false);
  const [repartidorId, setRepartidorId] = useState("");
  const [seleccion, setSeleccion] = useState<string[]>([]);
  const [optimizar, setOptimizar] = useState(true);
  const [enviando, setEnviando] = useState(false);

  const reiniciar = () => {
    setRepartidorId("");
    setSeleccion([]);
    setOptimizar(true);
  };

  const alternar = (id: string) => {
    setSeleccion((s) => (s.includes(id) ? s.filter((v) => v !== id) : [...s, id]));
  };

  const crear = async () => {
    if (!repartidorId || seleccion.length === 0) {
      toast("Elige un repartidor y al menos un pedido.");
      return;
    }
    setEnviando(true);
    try {
      await apiDelivery.crearRuta({
        sucursal_id: sucursalId,
        repartidor_id: repartidorId,
        venta_ids: seleccion,
        optimizar,
      });
      toast("Ruta creada.");
      setAbierto(false);
      reiniciar();
      onCreada();
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "No se pudo crear la ruta.");
    } finally {
      setEnviando(false);
    }
  };

  const items = Object.fromEntries(repartidores.map((r) => [r.id, etiquetaRepartidor(r)]));

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        setAbierto(v);
        if (!v) reiniciar();
      }}
    >
      <DialogTrigger
        render={<Button disabled={repartidores.length === 0 || sinAsignar.length === 0} />}
      >
        + Nueva ruta
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nueva ruta</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="repartidor">Repartidor</Label>
            <Select
              items={items}
              value={repartidorId}
              onValueChange={(v) => setRepartidorId(String(v))}
            >
              <SelectTrigger id="repartidor">
                <SelectValue placeholder="Elige un repartidor" />
              </SelectTrigger>
              <SelectContent>
                {repartidores.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {etiquetaRepartidor(r)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Pedidos</Label>
            <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded border border-border p-2">
              {sinAsignar.map((v) => (
                <Label
                  key={v.id}
                  className="flex cursor-pointer items-center gap-2 font-normal"
                >
                  <Checkbox
                    checked={seleccion.includes(v.id)}
                    onCheckedChange={() => alternar(v.id)}
                  />
                  <span className="truncate">{etiquetaVenta(v)}</span>
                </Label>
              ))}
            </div>
          </div>

          <Label className="flex cursor-pointer items-center gap-2 font-normal">
            <Checkbox checked={optimizar} onCheckedChange={(v) => setOptimizar(Boolean(v))} />
            Optimizar el orden de las paradas
          </Label>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setAbierto(false)}>
            Cancelar
          </Button>
          <Button type="button" onClick={crear} disabled={enviando}>
            {enviando ? "Creando…" : "Crear ruta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
