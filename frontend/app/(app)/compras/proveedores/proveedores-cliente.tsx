"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import { PersonaPicker } from "@/components/persona-picker/persona-picker";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearProveedorAction, type EstadoProveedor } from "./actions";

export type Proveedor = {
  id: string;
  tipo: string;
  persona_id: string | null;
  razon_social: string | null;
  ruc: string | null;
  formal: boolean;
  clasificacion: string;
  condicion_pago: string;
  activo: boolean;
};
export type Persona = { id: string; nombres: string; apellidos: string };

const ESTADO_INICIAL: EstadoProveedor = { error: "", ok: false };

function CamposJuridico() {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Razón social
        <input name="razon_social" required maxLength={255} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        RUC
        <input name="ruc" required maxLength={11} minLength={11} inputMode="numeric" />
      </label>
    </>
  );
}

function DialogoNuevoProveedor() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [tipo, setTipo] = useState<"juridico" | "natural">("juridico");
  const [estado, formAction, pendiente] = useActionState(crearProveedorAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      setTipo("juridico");
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
        + Nuevo proveedor
      </button>
      {/* `<dialog>` nativo: overlay, foco atrapado y cierre con Esc vienen
          gratis del navegador — sin instalar shadcn/ui para el primer form
          (YAGNI, se agrega cuando un caso lo pida de verdad). */}
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => {
          formRef.current?.reset();
          setTipo("juridico");
        }}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nuevo proveedor</h2>
          <div className="flex gap-4 text-sm font-semibold">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="tipo"
                value="juridico"
                checked={tipo === "juridico"}
                onChange={() => setTipo("juridico")}
              />
              Jurídico (RUC)
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="tipo"
                value="natural"
                checked={tipo === "natural"}
                onChange={() => setTipo("natural")}
              />
              Natural (persona)
            </label>
          </div>
          {tipo === "juridico" ? (
            <CamposJuridico />
          ) : (
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Persona (debe existir de antes)
              <PersonaPicker name="persona_id" />
            </label>
          )}
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Condición de pago
            <select name="condicion_pago" defaultValue="contado">
              <option value="contado">Contado</option>
              <option value="credito">Crédito</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Plazo de crédito (días)
            <input name="plazo_dias_credito" type="number" min={1} placeholder="Solo si es crédito" />
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

export function ProveedoresCliente({
  proveedores,
  personas,
}: {
  proveedores: Proveedor[];
  personas: Persona[];
}) {
  const nombrePersona = useMemo(
    () => new Map(personas.map((p) => [p.id, `${p.apellidos}, ${p.nombres}`])),
    [personas],
  );

  const columnas: ColumnDef<Proveedor>[] = useMemo(
    () => [
      {
        id: "nombre",
        header: "Proveedor",
        accessorFn: (p) =>
          p.tipo === "natural"
            ? (p.persona_id && nombrePersona.get(p.persona_id)) || "(persona sin resolver)"
            : (p.razon_social ?? "—"),
      },
      {
        id: "identificacion",
        header: "RUC / Doc.",
        accessorFn: (p) => p.ruc ?? "—",
      },
      { accessorKey: "tipo", header: "Tipo" },
      { accessorKey: "condicion_pago", header: "Condición de pago" },
      { accessorKey: "clasificacion", header: "Clasificación" },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<boolean>() ? "Activo" : "Inactivo"}
          </span>
        ),
      },
    ],
    [nombrePersona],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Proveedores</h1>
        <DialogoNuevoProveedor />
      </div>
      <TablaDatos columnas={columnas} datos={proveedores} placeholderBusqueda="Buscar proveedor..." />
    </div>
  );
}
