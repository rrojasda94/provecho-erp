"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { AvisoRecortado } from "@/components/estado/aviso-recortado";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import { crearChecklistAction } from "./actions";

import type { Almacen } from "../ordenes-cliente";

export type EquipoFrioOut = {
  equipo: string;
  temperatura_c: string;
  rango_min: string;
  rango_max: string;
  dentro_rango: boolean;
};

export type Checklist = {
  id: string;
  almacen_id: string;
  fecha: string;
  turno: string;
  bioseguridad_ok: boolean;
  superficies_ok: boolean;
  limpieza_intermedia_ok: boolean;
  equipos_frio: EquipoFrioOut[];
  plaga_indicio: boolean;
  estado: string;
};

const ETIQUETA_ESTADO: Record<string, string> = {
  aprobado: "Aprobado",
  bloqueado: "Bloqueado",
};

type LineaEquipo = {
  clave: number;
  equipo: string;
  temperatura: string;
  rangoMin: string;
  rangoMax: string;
};

function DialogoNuevoChecklist({ almacenes }: { almacenes: Almacen[] }) {
  const [equipos, setEquipos] = useState<LineaEquipo[]>([]);

  const editar = (clave: number, campo: keyof LineaEquipo, valor: string) =>
    setEquipos((prev) => prev.map((e) => (e.clave === clave ? { ...e, [campo]: valor } : e)));

  return (
    <DialogoFormulario
      titulo="Nuevo checklist de turno"
      disparador="+ Nuevo checklist"
      etiquetaEnvio="Registrar"
      etiquetaPendiente="Registrando..."
      accion={crearChecklistAction}
      ancho="max-w-xl"
      ayuda="Bioseguridad, superficies, limpieza intermedia y equipos de frío (RN-CDP-002/005). Cualquier falla bloquea la cocina: no admite orden ni consumo nuevo hasta un checklist aprobado."
      alAbrir={() => setEquipos([])}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir almacén..."
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Fecha
          <input
            name="fecha"
            type="date"
            required
            defaultValue={new Date().toISOString().slice(0, 10)}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Turno
          <input name="turno" placeholder="mañana, tarde, noche..." maxLength={30} required />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input name="bioseguridad_ok" type="checkbox" defaultChecked />
        Bioseguridad OK
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input name="superficies_ok" type="checkbox" defaultChecked />
        Superficies OK
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input name="limpieza_intermedia_ok" type="checkbox" defaultChecked />
        Limpieza intermedia OK
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input name="plaga_indicio" type="checkbox" />
        Indicio de plaga (RN-CDP-002)
      </label>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold">Equipos de frío</span>
        <span className="text-xs font-normal text-muted-foreground">
          Cada equipo fuera de su rango bloquea el checklist entero — el servidor decide
          `dentro_rango`, no se tipea a mano.
        </span>
        {equipos.map((linea) => (
          <div key={linea.clave} className="flex items-end gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
              Equipo
              <input
                name="equipo_nombre"
                required
                value={linea.equipo}
                onChange={(e) => editar(linea.clave, "equipo", e.target.value)}
              />
            </label>
            <label className="flex w-24 flex-col gap-1 text-xs font-semibold">
              Temp. °C
              <input
                name="equipo_temperatura"
                type="number"
                step="0.1"
                required
                value={linea.temperatura}
                onChange={(e) => editar(linea.clave, "temperatura", e.target.value)}
              />
            </label>
            <label className="flex w-20 flex-col gap-1 text-xs font-semibold">
              Mín.
              <input
                name="equipo_rango_min"
                type="number"
                step="0.1"
                required
                value={linea.rangoMin}
                onChange={(e) => editar(linea.clave, "rangoMin", e.target.value)}
              />
            </label>
            <label className="flex w-20 flex-col gap-1 text-xs font-semibold">
              Máx.
              <input
                name="equipo_rango_max"
                type="number"
                step="0.1"
                required
                value={linea.rangoMax}
                onChange={(e) => editar(linea.clave, "rangoMax", e.target.value)}
              />
            </label>
            <button
              type="button"
              aria-label="Quitar equipo"
              onClick={() => setEquipos((prev) => prev.filter((e) => e.clave !== linea.clave))}
              className="pb-1.5 text-muted-foreground hover:text-status-danger"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setEquipos((prev) => [
              ...prev,
              {
                clave: (prev.at(-1)?.clave ?? 0) + 1,
                equipo: "",
                temperatura: "",
                rangoMin: "",
                rangoMax: "",
              },
            ])
          }
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar equipo
        </button>
      </div>
    </DialogoFormulario>
  );
}

export function InocuidadCliente({
  checklists,
  total,
  almacenes,
}: {
  checklists: Checklist[];
  /** Cuántos hay en total: la página viene recortada. */
  total: number;
  almacenes: Almacen[];
}) {
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );

  const columnas: ColumnDef<Checklist>[] = useMemo(
    () => [
      { id: "fecha", header: "Fecha", accessorKey: "fecha" },
      { id: "turno", header: "Turno", accessorKey: "turno" },
      {
        id: "almacen",
        header: "Almacén",
        accessorFn: (c) => nombreAlmacen.get(c.almacen_id) ?? "—",
      },
      {
        id: "equipos",
        header: "Equipos de frío",
        accessorFn: (c) =>
          c.equipos_frio.length === 0
            ? "—"
            : c.equipos_frio.map((e) => `${e.equipo} (${e.temperatura_c}°C)`).join(", "),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          const clase =
            estado === "bloqueado" ? "bg-secondary/15 text-secondary" : "bg-accent/30 text-dark";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {ETIQUETA_ESTADO[estado] ?? estado}
            </span>
          );
        },
      },
    ],
    [nombreAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Inocuidad de turno</h1>
        <DialogoNuevoChecklist almacenes={almacenes} />
      </div>
      <p className="text-sm text-gray">
        Sin un checklist aprobado del día en el almacén, la cocina no admite orden nueva ni
        consumo (RN-CDP-002/005): un equipo de frío fuera de rango o indicio de plaga bloquea
        todo hasta el próximo checklist aprobado.
      </p>
      <AvisoRecortado
        mostrados={checklists.length}
        total={total}
        sugerencia="Acota por almacén, fecha o estado para ver el resto."
      />
      <TablaDatos
        columnas={columnas}
        datos={checklists}
        placeholderBusqueda="Buscar checklist..."
      />
    </div>
  );
}
