"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef } from "react";

import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearTrabajadorAction, type EstadoTrabajador } from "./actions";

export type Trabajador = {
  id: string;
  persona_id: string;
  cargo: string;
  area: string;
  tipo_vinculo: string;
  fecha_ingreso: string;
  fecha_cese: string | null;
  estado: string;
};
export type Persona = {
  id: string;
  nombres: string;
  apellidos: string;
  numero_documento: string | null;
};

const TIPOS_VINCULO = ["planilla", "practicante", "locacion_servicios"] as const;

const ESTADO_INICIAL: EstadoTrabajador = { error: "", ok: false };

function DialogoNuevoTrabajador() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearTrabajadorAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nuevo trabajador
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => formRef.current?.reset()}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nuevo trabajador</h2>
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
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </dialog>
    </>
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
