"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useRef } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearProveedorAction, type EstadoProveedor } from "./actions";

export type Proveedor = {
  id: string;
  tipo: string;
  razon_social: string | null;
  ruc: string | null;
  formal: boolean;
  clasificacion: string;
  condicion_pago: string;
  activo: boolean;
};

const columnas: ColumnDef<Proveedor>[] = [
  { accessorKey: "razon_social", header: "Razón social" },
  { accessorKey: "ruc", header: "RUC" },
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
];

const ESTADO_INICIAL: EstadoProveedor = { error: "", ok: false };

function DialogoNuevoProveedor() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearProveedorAction, ESTADO_INICIAL);

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
        + Nuevo proveedor
      </button>
      {/* `<dialog>` nativo: overlay, foco atrapado y cierre con Esc vienen
          gratis del navegador — sin instalar shadcn/ui para el primer form
          (YAGNI, se agrega cuando un caso lo pida de verdad). */}
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => formRef.current?.reset()}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nuevo proveedor</h2>
          <p className="-mt-2 text-xs text-gray">
            Proveedor jurídico. Para proveedor natural, contactar a Compras por ahora.
          </p>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Razón social
            <input name="razon_social" required maxLength={255} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            RUC
            <input name="ruc" required maxLength={11} minLength={11} inputMode="numeric" />
          </label>
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

export function ProveedoresCliente({ proveedores }: { proveedores: Proveedor[] }) {
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
