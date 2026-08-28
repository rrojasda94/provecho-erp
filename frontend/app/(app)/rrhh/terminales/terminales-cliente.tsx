"use client";

/**
 * Alta y revocación del dispositivo autorizado a marcar por un local
 * (ADR-073, RN-RRHH-023). No es `DialogoFormulario`: el alta devuelve un
 * código de activación que solo se ve una vez, y ese diálogo cierra solo
 * al terminar — se perdería antes de que alguien lo copie.
 */

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useMemo, useState, useTransition } from "react";

import { BOTON_FILA } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearTerminalAction, type EstadoTerminal, revocarTerminalAction } from "./actions";

export type Sucursal = { id: string; nombre: string };
export type Terminal = {
  id: string;
  sucursal_id: string;
  nombre: string;
  activo: boolean;
  ultima_marcacion_en: string | null;
};

const ESTADO_INICIAL: EstadoTerminal = { error: "", ok: false };

function FormularioNuevoTerminal({ sucursales }: { sucursales: Sucursal[] }) {
  const [estado, accion, pendiente] = useActionState(crearTerminalAction, ESTADO_INICIAL);
  // El código de la última alta que ya se dio por vista. Se compara contra
  // `estado.codigo` en vez de un booleano aparte: derivar de los datos que
  // ya hay evita el `useEffect` + `setState` que dispararía un render de
  // más por cada alta.
  const [codigoVisto, setCodigoVisto] = useState<string | null>(null);
  const mostrarCodigo = estado.ok && !!estado.codigo && estado.codigo !== codigoVisto;

  if (mostrarCodigo) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-primary/5 p-4 text-sm">
        <p className="font-semibold">Terminal «{estado.terminalNombre}» creado.</p>
        <p>
          Código de activación:{" "}
          <strong className="font-mono text-lg tracking-widest">{estado.codigo}</strong>
        </p>
        <p className="text-xs text-gray">
          Vale 30 minutos y una sola vez. Tecléalo en el pad de esa tablet
          (pantalla de activación) para enrolarla — de acá en más este
          código ya no sirve, y el pad se queda con su propio secreto.
        </p>
        <button
          type="button"
          className={BOTON_FILA}
          onClick={() => setCodigoVisto(estado.codigo ?? null)}
        >
          + Nuevo terminal
        </button>
      </div>
    );
  }

  return (
    <form action={accion} className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Sucursal
        <select name="sucursal_id" required defaultValue="">
          <option value="" disabled>
            Elige la sucursal...
          </option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre del terminal
        <input name="nombre" required maxLength={80} placeholder="Pasillo cocina" />
      </label>
      <button
        type="submit"
        disabled={pendiente || sucursales.length === 0}
        className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50"
      >
        {pendiente ? "Creando..." : "+ Nuevo terminal"}
      </button>
      {estado.error && <p className="w-full text-sm text-red-600">{estado.error}</p>}
    </form>
  );
}

function BotonRevocar({ terminalId }: { terminalId: string }) {
  const [pendiente, iniciar] = useTransition();
  return (
    <button
      type="button"
      className={BOTON_FILA}
      disabled={pendiente}
      onClick={() => iniciar(() => revocarTerminalAction(terminalId))}
    >
      {pendiente ? "Revocando..." : "Revocar"}
    </button>
  );
}

export function TerminalesCliente({
  terminales,
  sucursales,
}: {
  terminales: Terminal[];
  sucursales: Sucursal[];
}) {
  const nombreSucursal = useMemo(
    () => new Map(sucursales.map((s) => [s.id, s.nombre])),
    [sucursales],
  );

  const columnas: ColumnDef<Terminal>[] = useMemo(
    () => [
      {
        id: "sucursal",
        header: "Sucursal",
        accessorFn: (t) => nombreSucursal.get(t.sucursal_id) ?? "—",
      },
      { accessorKey: "nombre", header: "Terminal" },
      {
        id: "estado",
        header: "Estado",
        accessorFn: (t) => (t.activo ? "Activo" : "Sin enrolar"),
      },
      {
        id: "ultima",
        header: "Última marcación",
        accessorFn: (t) =>
          t.ultima_marcacion_en
            ? new Date(t.ultima_marcacion_en).toLocaleString("es-PE")
            : "—",
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <BotonRevocar terminalId={row.original.id} />,
      },
    ],
    [nombreSucursal],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Terminales de marcaje
        </h1>
      </div>
      <p className="text-sm text-gray">
        El dispositivo autorizado a marcar asistencia por un local (ADR-073).
        Sin uno enrolado, el pad no marca aunque el PIN sea correcto — es lo
        que evita que alguien marque desde fuera del local. Revocar uno
        (tablet perdida o dada de baja) lo desactiva en el acto.
      </p>
      <FormularioNuevoTerminal sucursales={sucursales} />
      <TablaDatos
        columnas={columnas}
        datos={terminales}
        placeholderBusqueda="Buscar por sucursal o terminal..."
      />
    </div>
  );
}
