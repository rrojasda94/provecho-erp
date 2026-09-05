"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { tienePermiso } from "@/lib/permisos";

import { liberarReservaAction } from "./actions";

export type Reserva = {
  id: string;
  almacen_id: string;
  sku_id: string;
  cantidad: string;
  tipo: string;
  referencia_id: string | null;
  motivo: string | null;
  estado: string;
};
export type OpcionAlmacen = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string };

/** Quién apartó el stock. El tipo decide además si se puede soltar desde
 * acá: una merma tiene su propia pantalla, con su propia firma. */
const ETIQUETA_TIPO: Record<string, string> = {
  solicitud: "Un requerimiento",
  merma: "Una merma",
  produccion: "Una orden de producción",
  carrito: "Un pedido en curso",
};

/**
 * Reservas: el stock que está en el almacén pero ya tiene dueño.
 *
 * Era la mitad invisible de `GET /stock`. La columna «Reservado» decía
 * cuánto, y no había forma de saber **de quién** ni de soltarlo: los dos
 * endpoints existían sin un solo llamador, y `inventory.liberar_reserva`
 * era un permiso sembrado que nadie podía ejercer. Una reserva colgada de un
 * requerimiento viejo se soltaba llamando la API a mano.
 *
 * Las mermas no se liberan desde acá aunque también sean reservas: se
 * resuelven en su pantalla, donde la decisión es desechar o reintegrar y la
 * firma otra persona (ADR-028).
 */
export function ReservasCliente({
  reservas,
  almacenes,
  skus,
  permisos,
}: {
  reservas: Reserva[];
  almacenes: OpcionAlmacen[];
  skus: OpcionSku[];
  permisos: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState("");
  const puedeLiberar = tienePermiso(permisos, "inventory.liberar_reserva");

  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );
  const nombreSku = useMemo(() => new Map(skus.map((s) => [s.id, s.etiqueta])), [skus]);

  async function liberar(id: string) {
    setEnviando(id);
    setError("");
    const r = await liberarReservaAction(id);
    if (!r.ok) setError(r.error);
    else router.refresh();
    setEnviando("");
  }

  const columnas = useMemo<ColumnDef<Reserva>[]>(
    () => [
      {
        header: "Almacén",
        accessorFn: (r) => nombreAlmacen.get(r.almacen_id) ?? "—",
      },
      { header: "Qué", accessorFn: (r) => nombreSku.get(r.sku_id) ?? r.sku_id },
      { header: "Cantidad", accessorKey: "cantidad", meta: { numero: true } },
      {
        header: "Para qué",
        accessorFn: (r) => ETIQUETA_TIPO[r.tipo] ?? r.tipo,
      },
      { header: "Motivo", accessorFn: (r) => r.motivo ?? "—" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          !puedeLiberar || row.original.tipo === "merma" ? null : (
            <button
              type="button"
              disabled={enviando === row.original.id}
              onClick={() => liberar(row.original.id)}
              title="Devuelve la cantidad al disponible del almacén"
              className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
            >
              Liberar
            </button>
          ),
      },
    ],
    // `liberar` se recrea en cada render; lo que cambia las columnas es quién
    // puede liberar, qué fila está enviando y los catálogos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [puedeLiberar, enviando, nombreAlmacen, nombreSku],
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">Reservas</h1>
        <p className="text-xs text-gray">
          Stock que sigue en el almacén pero ya está prometido, así que no figura
          en el disponible (RN-INV-009). Liberar una lo devuelve al disponible:
          es lo que se hace cuando el pedido que la creó ya no va.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      <TablaDatos
        columnas={columnas}
        datos={reservas}
        placeholderBusqueda="Buscar por almacén o motivo..."
        vacio="No hay stock reservado."
      />
    </div>
  );
}
