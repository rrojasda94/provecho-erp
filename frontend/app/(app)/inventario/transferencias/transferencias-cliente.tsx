"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { tienePermiso } from "@/lib/permisos";

import { recibirTransferenciaAction } from "./actions";

export type Transferencia = {
  id: string;
  origen_almacen_id: string;
  destino_almacen_id: string;
  solicitud_id: string | null;
  estado: string;
  observacion: string | null;
};

const TONO: Record<string, "exito" | "peligro" | "neutro"> = {
  en_transito: "peligro",
  recibida: "exito",
};

/**
 * Traslados entre almacenes: lo que ya salió y todavía no llegó.
 *
 * La pantalla que faltaba. `despachar` y `recibir` existían en la API desde
 * el slice de transferencias y **ninguna** pantalla las llamaba: lo
 * despachado quedaba `en_transito` para siempre y el almacén que lo había
 * pedido no tenía dónde decir "llegó".
 */
export function TransferenciasCliente({
  transferencias,
  nombreDeAlmacen,
  permisos,
}: {
  transferencias: Transferencia[];
  nombreDeAlmacen: Record<string, string>;
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState("");
  const puedeRecibir = tienePermiso(permisos, "inventory.recepcion");

  async function recibir(id: string) {
    setEnviando(id);
    setError("");
    const r = await recibirTransferenciaAction(id);
    if (!r.ok) setError(r.error);
    else router.refresh();
    setEnviando("");
  }

  const columnas = useMemo<ColumnDef<Transferencia>[]>(
    () => [
      {
        header: "Sale de",
        accessorFn: (t) => nombreDeAlmacen[t.origen_almacen_id] ?? "—",
      },
      {
        header: "Va a",
        accessorFn: (t) => nombreDeAlmacen[t.destino_almacen_id] ?? "—",
      },
      {
        header: "Estado",
        accessorKey: "estado",
        cell: ({ row }) => (
          <Insignia tono={TONO[row.original.estado] ?? "neutro"}>
            {row.original.estado === "en_transito"
              ? "En tránsito"
              : row.original.estado}
          </Insignia>
        ),
      },
      {
        header: "Observación",
        accessorFn: (t) => t.observacion ?? "—",
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          row.original.estado !== "en_transito" || !puedeRecibir ? null : (
            <button
              type="button"
              disabled={enviando === row.original.id}
              onClick={() => recibir(row.original.id)}
              className="rounded bg-primary px-3 py-1 text-xs font-bold text-primary-foreground disabled:opacity-50"
            >
              Recibir
            </button>
          ),
      },
    ],
    // `recibir` se recrea en cada render; lo que cambia las columnas es quién
    // puede recibir y qué fila está enviando.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeRecibir, enviando, nombreDeAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Traslados
        </h1>
        <p className="text-xs text-gray">
          Lo que salió de un almacén hacia otro. Mientras está en tránsito el
          stock ya no está en el origen y todavía no está en el destino: lo
          pone ahí quien lo recibe.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      <TablaDatos
        columnas={columnas}
        datos={transferencias}
        placeholderBusqueda="Buscar por almacén o estado..."
        vacio="No hay traslados todavía. Se crean al despachar un requerimiento aprobado."
      />
    </div>
  );
}
