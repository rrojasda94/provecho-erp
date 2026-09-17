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
import {
  apiDelivery,
  ETIQUETA_VEHICULO,
  type Repartidor,
  type RutaConParadas,
  type VentaLista,
} from "@/lib/delivery";

/** Crear ruta y editar ruta comparten el mismo formulario (ADR-101): la
 * única diferencia real es qué universo de pedidos se ofrece —"sin
 * asignar" nada más al crear, más las paradas pendientes propias al
 * editar— y si hace falta elegir repartidor desde cero. */
type Props = {
  sucursalId: string;
  sinAsignar: VentaLista[];
  repartidores: Repartidor[];
  onListo: () => void;
  /** Presente = editar esa ruta; ausente = crear una nueva. */
  ruta?: RutaConParadas;
  trigger: {
    label: string;
    variant?: React.ComponentProps<typeof Button>["variant"];
    size?: React.ComponentProps<typeof Button>["size"];
    disabled?: boolean;
  };
};

type ParadaEditable = {
  id: string;
  numeroOrden: number | null;
  direccion: string | null;
  lista: boolean;
  distanciaKm: number | null;
};

function etiquetaRepartidor(r: Repartidor): string {
  const vehiculo = ETIQUETA_VEHICULO[r.vehiculo_tipo];
  return r.nombre ? `${r.nombre} (${vehiculo})` : vehiculo;
}

function resuelta(estado: string): boolean {
  return estado === "entregada" || estado === "fallida" || estado === "cancelada";
}

function deVentaLista(v: VentaLista): ParadaEditable {
  return {
    id: v.id,
    numeroOrden: v.numero_orden,
    direccion: v.direccion_entrega,
    lista: v.lista,
    distanciaKm: v.distancia_entrega_km ? Number(v.distancia_entrega_km) : null,
  };
}

/** `null` = puede enviarse. */
function errorDeValidacion(
  editando: boolean,
  repartidorId: string,
  seleccion: string[],
  fijasCount: number,
): string | null {
  if (!editando && (!repartidorId || seleccion.length === 0)) {
    return "Elige un repartidor y al menos un pedido.";
  }
  if (editando && fijasCount + seleccion.length === 0) {
    return "La ruta necesita al menos una parada.";
  }
  return null;
}

function ParadasFijas({ fijas }: { fijas: RutaConParadas["paradas"] }) {
  if (fijas.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <Label>Ya resueltas (no se pueden tocar)</Label>
      <ul className="flex flex-col gap-1 rounded border border-border p-2 text-sm text-gray">
        {fijas.map((p) => (
          <li key={p.entrega_id} className="truncate">
            #{p.numero_orden ?? "—"} · {p.direccion_entrega ?? "Sin dirección"}
          </li>
        ))}
      </ul>
    </div>
  );
}

function OpcionPedido({
  venta,
  marcada,
  bloqueada,
  onAlternar,
}: {
  venta: ParadaEditable;
  marcada: boolean;
  bloqueada: boolean;
  onAlternar: () => void;
}) {
  return (
    <Label
      className={`flex items-center gap-2 font-normal ${
        bloqueada ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      }`}
    >
      <Checkbox checked={marcada} disabled={bloqueada} onCheckedChange={onAlternar} />
      <span className="truncate">
        #{venta.numeroOrden ?? "—"} · {venta.direccion ?? "Sin dirección"}
        {venta.distanciaKm ? ` · ${venta.distanciaKm} km` : ""}
      </span>
      {!venta.lista ? (
        <span className="ml-auto shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
          En cocina
        </span>
      ) : null}
    </Label>
  );
}

function ListaPedidos({
  opciones,
  seleccion,
  enCurso,
  onAlternar,
}: {
  opciones: ParadaEditable[];
  seleccion: string[];
  enCurso: boolean;
  onAlternar: (venta: ParadaEditable) => void;
}) {
  if (opciones.length === 0) {
    return <p className="text-sm text-gray">No hay pedidos disponibles.</p>;
  }
  return (
    <>
      {opciones.map((v) => (
        <OpcionPedido
          key={v.id}
          venta={v}
          marcada={seleccion.includes(v.id)}
          bloqueada={enCurso && !v.lista && !seleccion.includes(v.id)}
          onAlternar={() => onAlternar(v)}
        />
      ))}
    </>
  );
}

export default function RutaDialogo({
  sucursalId,
  sinAsignar,
  repartidores,
  onListo,
  ruta,
  trigger,
}: Props) {
  const editando = ruta !== undefined;
  const enCurso = ruta?.estado === "en_curso";
  const fijas = ruta ? ruta.paradas.filter((p) => resuelta(p.estado)) : [];
  const pendientesDeRuta = ruta ? ruta.paradas.filter((p) => !resuelta(p.estado)) : [];
  const pendientesIds = pendientesDeRuta.map((p) => p.venta_id);

  // Universo de opciones: "sin asignar" siempre, más las paradas que ya
  // son de esta ruta cuando se edita — no son "sin asignar", son suyas.
  const opciones: ParadaEditable[] = [
    ...pendientesDeRuta.map((p) => ({
      id: p.venta_id,
      numeroOrden: p.numero_orden,
      direccion: p.direccion_entrega,
      lista: p.lista,
      distanciaKm: null as number | null,
    })),
    ...sinAsignar.map(deVentaLista),
  ];

  const [abierto, setAbierto] = useState(false);
  const [repartidorId, setRepartidorId] = useState(ruta?.repartidor_id ?? "");
  const [seleccion, setSeleccion] = useState<string[]>(pendientesIds);
  const [optimizar, setOptimizar] = useState(true);
  const [enviando, setEnviando] = useState(false);

  const reiniciar = () => {
    setRepartidorId(ruta?.repartidor_id ?? "");
    setSeleccion(pendientesIds);
    setOptimizar(true);
  };

  const alternar = (venta: ParadaEditable) => {
    const marcada = seleccion.includes(venta.id);
    // Una ruta que ya salió no suma pedidos que siguen en cocina — sí deja
    // sacar los que ya tenía, estén listos o no.
    if (enCurso && !venta.lista && !marcada) return;
    setSeleccion((s) => (marcada ? s.filter((v) => v !== venta.id) : [...s, venta.id]));
  };

  const guardar = () =>
    editando && ruta
      ? apiDelivery.editarParadas(ruta.id, {
          venta_ids: seleccion,
          optimizar,
          repartidor_id:
            repartidorId && repartidorId !== ruta.repartidor_id ? repartidorId : undefined,
        })
      : apiDelivery.crearRuta({
          sucursal_id: sucursalId,
          repartidor_id: repartidorId,
          venta_ids: seleccion,
          optimizar,
        });

  const confirmar = async () => {
    const error = errorDeValidacion(editando, repartidorId, seleccion, fijas.length);
    if (error) {
      toast(error);
      return;
    }
    setEnviando(true);
    try {
      await guardar();
      toast(editando ? "Ruta actualizada." : "Ruta creada.");
      setAbierto(false);
      reiniciar();
      onListo();
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "No se pudo guardar la ruta.");
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
        render={
          <Button variant={trigger.variant} size={trigger.size} disabled={trigger.disabled} />
        }
      >
        {trigger.label}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editando ? "Editar ruta" : "Nueva ruta"}</DialogTitle>
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

          <ParadasFijas fijas={fijas} />

          <div className="flex flex-col gap-1.5">
            <Label>Pedidos</Label>
            <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded border border-border p-2">
              <ListaPedidos
                opciones={opciones}
                seleccion={seleccion}
                enCurso={enCurso ?? false}
                onAlternar={alternar}
              />
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
          <Button type="button" onClick={confirmar} disabled={enviando}>
            {enviando ? "Guardando…" : editando ? "Guardar cambios" : "Crear ruta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
