"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  cesarTrabajadorAction,
  crearTrabajadorAction,
  editarTrabajadorAction,
} from "./actions";

export type Trabajador = {
  id: string;
  persona_id: string;
  cargo: string;
  area: string;
  tipo_vinculo: string;
  fecha_ingreso: string;
  fecha_cese: string | null;
  remuneracion_base: string | null;
  estado: string;
};
export type Persona = {
  id: string;
  nombres: string;
  apellidos: string;
  numero_documento: string | null;
};

const TIPOS_VINCULO = ["planilla", "practicante", "locacion_servicios"] as const;

function DialogoNuevoTrabajador() {
  return (
    <DialogoFormulario
      titulo="Nuevo trabajador"
      disparador="+ Nuevo trabajador"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearTrabajadorAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Persona (debe existir de antes)
        <PersonaPicker name="persona_id" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cargo
        <input name="cargo" required maxLength={100} placeholder="Cocinero" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Área
        <input name="area" required maxLength={100} placeholder="Cocina" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo de vínculo
        <select name="tipo_vinculo" defaultValue="planilla">
          {TIPOS_VINCULO.map((t) => (
            <option key={t} value={t}>
              {t.replace("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de ingreso
        <input name="fecha_ingreso" type="date" required />
      </label>
    </DialogoFormulario>
  );
}

/** Corrección del legajo: cargo, área, remuneración y suspensión.
 *
 * El nombre y el documento no están porque viven en la persona
 * (RN-GEN-007); el tipo de vínculo y la fecha de ingreso tampoco, porque
 * cambiarlos reescribe la historia laboral —eso es un contrato nuevo, no una
 * corrección—. */
function DialogoEditarTrabajador({ trabajador }: { trabajador: Trabajador }) {
  return (
    <DialogoFormulario
      titulo="Editar trabajador"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarTrabajadorAction}
      ayuda="Nombre y documento se corrigen en Usuarios → Personas. El vínculo y la fecha de ingreso no se editan: cambiarlos sería otro contrato."
    >
      <input type="hidden" name="id" value={trabajador.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cargo
        <input name="cargo" required maxLength={100} defaultValue={trabajador.cargo} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Área
        <input name="area" required maxLength={100} defaultValue={trabajador.area} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Remuneración base
        <input
          name="remuneracion_base"
          type="number"
          min={0}
          step="0.01"
          defaultValue={trabajador.remuneracion_base ?? ""}
          placeholder="O subvención, si es practicante"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Estado
        <select name="estado" defaultValue={trabajador.estado}>
          <option value="activo">Activo</option>
          <option value="suspendido">Suspendido</option>
        </select>
      </label>
    </DialogoFormulario>
  );
}

/** Cese: acción aparte porque fija la fecha y dispara la liquidación. */
function DialogoCesarTrabajador({ trabajador }: { trabajador: Trabajador }) {
  return (
    <DialogoFormulario
      titulo="Registrar cese"
      disparador="Cesar"
      claseDisparador={BOTON_FILA}
      etiquetaEnvio="Registrar cese"
      etiquetaPendiente="Registrando..."
      accion={cesarTrabajadorAction}
      ayuda="El cese fija la fecha y avisa a los módulos que dependen de ella. No se deshace desde acá."
    >
      <input type="hidden" name="id" value={trabajador.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha de cese
        <input name="fecha_cese" type="date" required />
      </label>
    </DialogoFormulario>
  );
}

export function TrabajadoresCliente({
  trabajadores,
  personas,
}: {
  trabajadores: Trabajador[];
  personas: Persona[];
}) {
  const nombrePersona = useMemo(
    () => new Map(personas.map((p) => [p.id, `${p.apellidos}, ${p.nombres}`])),
    [personas],
  );

  const columnas: ColumnDef<Trabajador>[] = useMemo(
    () => [
      {
        id: "persona",
        header: "Nombre",
        accessorFn: (t) => nombrePersona.get(t.persona_id) ?? "—",
      },
      { accessorKey: "cargo", header: "Cargo" },
      { accessorKey: "area", header: "Área" },
      {
        accessorKey: "tipo_vinculo",
        header: "Vínculo",
        cell: ({ getValue }) => getValue<string>().replace("_", " "),
      },
      { accessorKey: "fecha_ingreso", header: "Ingreso" },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<string>() === "activo"
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<string>()}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        // Un cesado no se edita ni se vuelve a cesar: ofrecer el control
        // solo invita al 409 (mismo criterio que Producción).
        cell: ({ row }) =>
          row.original.estado === "cesado" ? null : (
            <div className="flex gap-1.5">
              <DialogoEditarTrabajador trabajador={row.original} />
              <DialogoCesarTrabajador trabajador={row.original} />
            </div>
          ),
      },
    ],
    [nombrePersona],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Trabajadores</h1>
        <DialogoNuevoTrabajador />
      </div>
      <TablaDatos
        columnas={columnas}
        datos={trabajadores}
        placeholderBusqueda="Buscar trabajador..."
      />
    </div>
  );
}
