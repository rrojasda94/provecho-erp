"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearCuentaAction, type EstadoAsiento } from "../actions";
import type { Cuenta } from "../asientos-cliente";

const ESTADO_INICIAL: EstadoAsiento = { error: "", ok: false };

// Los cinco del modelo contable; la naturaleza (deudora/acreedora) la deriva
// el backend del tipo, no se teclea.
const TIPOS = ["activo", "pasivo", "patrimonio", "ingreso", "gasto"] as const;

function DialogoNuevaCuenta({ cuentas }: { cuentas: Cuenta[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearCuentaAction, ESTADO_INICIAL);

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
        + Nueva cuenta
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nueva cuenta</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código
            <input name="codigo" required maxLength={20} placeholder="ej. 42111" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input name="nombre" required maxLength={150} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo
            <select name="tipo" defaultValue="activo">
              {TIPOS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Cuenta padre
            <select name="cuenta_padre_id" defaultValue="">
              <option value="">Sin padre (cuenta de primer nivel)</option>
              {cuentas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.codigo} · {c.nombre}
                </option>
              ))}
            </select>
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

export function PlanCuentasCliente({ cuentas }: { cuentas: Cuenta[] }) {
  const columnas: ColumnDef<Cuenta>[] = useMemo(
    () => [
      { accessorKey: "codigo", header: "Código" },
      { accessorKey: "nombre", header: "Nombre" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        accessorKey: "activa",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<boolean>() ? "Activa" : "Inactiva"}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Plan de cuentas</h1>
        <DialogoNuevaCuenta cuentas={cuentas} />
      </div>
      <p className="text-sm text-gray">
        Las cuentas contra las que se registran los asientos. El mapeo evento → cuentas
        (venta, compra, pago) se configura por API y usa estas mismas cuentas.
      </p>
      <TablaDatos columnas={columnas} datos={cuentas} placeholderBusqueda="Buscar cuenta..." />
    </div>
  );
}
