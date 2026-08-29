"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import { abrirBorradorAction } from "./actions";

export type Solicitud = {
  id: string;
  almacen_solicitante_id: string;
  almacen_abastecedor_id: string;
  estado: string;
  solicitado_por: string;
  aprobado_por: string | null;
  observacion: string | null;
};

export type OpcionAlmacen = { id: string; nombre: string };
type Opcion = { id: string; nombre: string };

/** Los estados que el usuario puede pedir. `borrador` no está: la lista de
 * la jornada se abre por su botón, no filtrando un listado. */
const ESTADOS = [
  ["", "Todos los estados"],
  ["pendiente", "Esperando aprobación"],
  ["aprobada", "Aprobadas"],
  ["despachada", "Despachadas"],
  ["recibida", "Recibidas"],
  ["rechazada", "Rechazadas"],
  ["cancelada", "Canceladas"],
] as const;

export function SolicitudesCliente({
  solicitudes,
  almacenes,
  sucursales,
  marcas,
  nombreDeAlmacen,
  filtros,
  permisos,
}: {
  solicitudes: Solicitud[];
  almacenes: OpcionAlmacen[];
  sucursales: Opcion[];
  marcas: Opcion[];
  nombreDeAlmacen: Record<string, string>;
  filtros: { almacen: string; estado: string; sucursal: string; marca: string };
  permisos: string[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState("");
  const [almacenDelBorrador, setAlmacenDelBorrador] = useState(
    filtros.almacen || almacenes[0]?.id || "",
  );
  const [abriendo, abrir] = useTransition();

  const puedeSolicitar = tienePermiso(permisos, "inventory.solicitar_insumos");

  const filtrar = (campo: string, valor: string) => {
    const nuevos = new URLSearchParams(params.toString());
    if (valor) nuevos.set(campo, valor);
    else nuevos.delete(campo);
    router.push(`/inventario/solicitudes?${nuevos}`);
  };

  const abrirRequerimiento = () => {
    setError("");
    abrir(async () => {
      const r = await abrirBorradorAction(almacenDelBorrador);
      // Con éxito la acción redirige y este código no llega a correr.
      if (r && !r.ok) setError(r.error);
    });
  };

  const columnas = useMemo<ColumnDef<Solicitud>[]>(
    () => [
      {
        header: "Almacén que pide",
        accessorFn: (s) => nombreDeAlmacen[s.almacen_solicitante_id] ?? "—",
        cell: ({ row }) => (
          <Link
            href={`/inventario/solicitudes/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {nombreDeAlmacen[row.original.almacen_solicitante_id] ?? "—"}
          </Link>
        ),
      },
      {
        header: "Se abastece de",
        accessorFn: (s) => nombreDeAlmacen[s.almacen_abastecedor_id] ?? "—",
      },
      { header: "Estado", accessorKey: "estado" },
      {
        header: "Observación",
        accessorFn: (s) => s.observacion ?? "—",
      },
    ],
    [nombreDeAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">
            Requerimientos
          </h1>
          <p className="text-xs text-gray">
            Lo que cada local le pide a su abastecedor. El requerimiento de la
            jornada se abre con lo que ya está bajo mínimo.
          </p>
        </div>

        {puedeSolicitar && (
          <div className="flex items-end gap-2">
            <label className="flex flex-col gap-1 text-xs font-semibold">
              Almacén
              <Combobox
                etiqueta="Almacén del requerimiento"
                requerido
                value={almacenDelBorrador}
                alCambiar={(v) => v && setAlmacenDelBorrador(v)}
                opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
              />
            </label>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50"
              onClick={abrirRequerimiento}
              disabled={abriendo || !almacenDelBorrador}
            >
              {abriendo ? "Abriendo..." : "Requerimiento de la jornada"}
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <Filtro
          etiqueta="Marca"
          valor={filtros.marca}
          opciones={marcas}
          alCambiar={(v) => filtrar("marca", v)}
        />
        <Filtro
          etiqueta="Sucursal"
          valor={filtros.sucursal}
          opciones={sucursales}
          alCambiar={(v) => filtrar("sucursal", v)}
        />
        <Filtro
          etiqueta="Almacén"
          valor={filtros.almacen}
          opciones={almacenes}
          alCambiar={(v) => filtrar("almacen", v)}
        />
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Estado
          <select
            value={filtros.estado}
            onChange={(e) => filtrar("estado", e.target.value)}
          >
            {ESTADOS.map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="text-sm text-secondary">{error}</p>}

      <TablaDatos
        columnas={columnas}
        datos={solicitudes}
        placeholderBusqueda="Buscar por almacén o estado..."
        vacio="No hay requerimientos con esos filtros."
      />
    </div>
  );
}

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
}: {
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  alCambiar: (valor: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold">
      {etiqueta}
      <Combobox
        etiqueta={etiqueta}
        marcador="Todas"
        value={valor}
        alCambiar={(v) => alCambiar(v ?? "")}
        opciones={opciones.map((o) => ({ valor: o.id, etiqueta: o.nombre }))}
      />
    </label>
  );
}
