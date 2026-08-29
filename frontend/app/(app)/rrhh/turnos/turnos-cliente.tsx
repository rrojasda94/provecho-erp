"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import { guardarTurnoAction } from "./actions";

export type Sucursal = { id: string; nombre: string };
export type Turno = {
  id: string;
  sucursal_id: string;
  nombre: string;
  hora_inicio: string;
  hora_fin: string;
  hora_limite_salida: string;
  tolerancia_min: number;
  activo: boolean;
};

/** La API devuelve `HH:MM:SS`; el `<input type="time">` y la tabla quieren
 * `HH:MM`. */
const hhmm = (h: string) => h.slice(0, 5);

function CamposTurno({
  sucursales,
  turno,
}: {
  sucursales: Sucursal[];
  turno?: Turno;
}) {
  const t: Partial<Turno> = turno ?? {};

  return (
    <>
      {turno ? (
        <p className="text-sm text-gray">
          Turno de{" "}
          <strong>{sucursales.find((s) => s.id === t.sucursal_id)?.nombre}</strong>.
          Un turno no se muda de local: las marcaciones ya medidas quedarían
          contra el horario de otro sitio.
        </p>
      ) : (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sucursal
          <Combobox
            name="sucursal_id"
            etiqueta="Sucursal"
            requerido
            marcador="Elige la sucursal..."
            opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
          />
        </label>
      )}

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input
          name="nombre"
          required
          maxLength={50}
          placeholder="Mañana"
          defaultValue={valor(t.nombre)}
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Entra
          <input
            type="time"
            name="hora_inicio"
            required
            defaultValue={t.hora_inicio ? hhmm(t.hora_inicio) : ""}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sale
          <input
            type="time"
            name="hora_fin"
            required
            defaultValue={t.hora_fin ? hhmm(t.hora_fin) : ""}
          />
        </label>
      </div>
      <span className="text-xs text-gray">
        Una hora de salida menor que la de entrada significa que el turno cruza la
        medianoche — el turno noche se configura así.
      </span>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tolerancia (minutos)
        <input
          type="number"
          name="tolerancia_min"
          min={0}
          max={120}
          defaultValue={t.tolerancia_min ?? 5}
        />
        <span className="text-xs font-normal text-gray">
          Los minutos de gracia antes de contar tardanza.
        </span>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Hora límite para marcar la salida
        <input
          type="time"
          name="hora_limite_salida"
          required
          defaultValue={t.hora_limite_salida ? hhmm(t.hora_limite_salida) : ""}
        />
        <span className="text-xs font-normal text-gray">
          Pasada esta hora sin marcación, el aviso le llega al trabajador, al
          encargado del local y a RRHH. No cierra la jornada ni genera horas
          extra: pide que la marquen.
        </span>
      </label>

      {turno && (
        <label className="flex items-center gap-2 text-sm font-semibold">
          <input type="checkbox" name="activo" defaultChecked={turno.activo} />
          Activo
        </label>
      )}
    </>
  );
}

function DialogoNuevoTurno({ sucursales }: { sucursales: Sucursal[] }) {
  return (
    <DialogoFormulario
      titulo="Nuevo turno"
      disparador="+ Nuevo turno"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarTurnoAction}
      envioDeshabilitado={sucursales.length === 0}
      ayuda={
        sucursales.length === 0
          ? "Primero da de alta una sucursal: un turno siempre es de un local."
          : undefined
      }
    >
      <CamposTurno sucursales={sucursales} />
    </DialogoFormulario>
  );
}

function DialogoEditarTurno({
  turno,
  sucursales,
}: {
  turno: Turno;
  sucursales: Sucursal[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar turno"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarTurnoAction}
      ayuda="Cambiar el horario no reescribe lo ya marcado: cada asistencia guardó su tardanza al momento de marcarse."
    >
      <input type="hidden" name="id" value={turno.id} />
      <CamposTurno sucursales={sucursales} turno={turno} />
    </DialogoFormulario>
  );
}

export function TurnosCliente({
  turnos,
  sucursales,
}: {
  turnos: Turno[];
  sucursales: Sucursal[];
}) {
  const nombreSucursal = useMemo(
    () => new Map(sucursales.map((s) => [s.id, s.nombre])),
    [sucursales],
  );

  const columnas: ColumnDef<Turno>[] = useMemo(
    () => [
      {
        id: "sucursal",
        header: "Sucursal",
        accessorFn: (t) => nombreSucursal.get(t.sucursal_id) ?? "—",
      },
      { accessorKey: "nombre", header: "Turno" },
      {
        id: "horario",
        header: "Horario",
        accessorFn: (t) => `${hhmm(t.hora_inicio)} – ${hhmm(t.hora_fin)}`,
      },
      {
        id: "tolerancia",
        header: "Tolerancia",
        accessorFn: (t) => `${t.tolerancia_min} min`,
      },
      {
        id: "limite",
        header: "Límite de salida",
        accessorFn: (t) => hhmm(t.hora_limite_salida),
      },
      {
        id: "estado",
        header: "Estado",
        accessorFn: (t) => (t.activo ? "Activo" : "Inactivo"),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarTurno turno={row.original} sucursales={sucursales} />
        ),
      },
    ],
    [nombreSucursal, sucursales],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Turnos de trabajo
        </h1>
        <DialogoNuevoTurno sucursales={sucursales} />
      </div>
      <p className="text-sm text-gray">
        El horario laboral de cada local: contra esto se mide la tardanza al
        marcar en el pad y hasta cuándo hay que marcar la salida. Distinto del
        turno de caja, que es la sesión de una caja abierta.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={turnos}
        placeholderBusqueda="Buscar por sucursal o turno..."
      />
    </div>
  );
}
