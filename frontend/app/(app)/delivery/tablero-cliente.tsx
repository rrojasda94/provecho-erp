"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorApi } from "@/lib/cliente-api";
import { apiDelivery, type Repartidor, type Tablero, type VentaLista } from "@/lib/delivery";

import NuevaRutaDialogo from "./nueva-ruta-dialogo";
import TarjetaRuta from "./tarjeta-ruta";
import { useTablero } from "./use-tablero";

type Props = {
  inicial: Tablero;
  sucursalId: string;
  sucursales: { id: string; nombre: string }[];
  puedeDespachar: boolean;
  repartidores: Repartidor[];
};

function TarjetaSinAsignar({ venta }: { venta: VentaLista }) {
  return (
    <li className="rounded-lg border border-border bg-card p-3 text-sm">
      <p className="font-medium">#{venta.numero_orden}</p>
      <p className="text-gray">{venta.direccion_entrega ?? "Sin dirección anotada"}</p>
      {venta.distancia_entrega_km ? (
        <p className="text-xs text-gray">{venta.distancia_entrega_km} km</p>
      ) : null}
    </li>
  );
}

export default function TableroCliente({
  inicial,
  sucursalId,
  sucursales,
  puedeDespachar,
  repartidores,
}: Props) {
  const router = useRouter();
  const { tablero, refrescar } = useTablero(sucursalId, inicial);

  const cancelar = async (rutaId: string) => {
    try {
      await apiDelivery.cancelarRuta(rutaId);
      refrescar();
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "No se pudo cancelar la ruta.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-xl text-dark">Tablero de despacho</h1>
        <div className="flex items-center gap-3">
          {sucursales.length > 1 ? (
            <Select value={sucursalId} onValueChange={(v) => router.push(`/delivery?sucursal=${v}`)}>
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sucursales.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          {puedeDespachar ? (
            <NuevaRutaDialogo
              sucursalId={sucursalId}
              sinAsignar={tablero.sin_asignar}
              repartidores={repartidores}
              onCreada={refrescar}
            />
          ) : null}
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-gray">
          Sin asignar ({tablero.sin_asignar.length})
        </h2>
        {tablero.sin_asignar.length === 0 ? (
          <p className="text-sm text-gray">No hay pedidos delivery listos sin asignar.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {tablero.sin_asignar.map((venta) => (
              <TarjetaSinAsignar key={venta.id} venta={venta} />
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-gray">Rutas en curso ({tablero.rutas.length})</h2>
        {tablero.rutas.length === 0 ? (
          <p className="text-sm text-gray">No hay rutas vivas en esta sucursal.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {tablero.rutas.map((ruta) => (
              <TarjetaRuta
                key={ruta.id}
                ruta={ruta}
                puedeDespachar={puedeDespachar}
                onCancelar={cancelar}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
