"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { ejecutarPagoAction, rechazarPagoAction, type EstadoAsiento } from "../actions";

export type Pago = {
  id: string;
  concepto: string;
  proveedor_id: string | null;
  orden_compra_id: string | null;
  monto: string;
  monto_detraccion: string | null;
  medio_pago: string | null;
  estado: string;
  fecha_ejecucion: string | null;
  constancia: string | null;
};
export type Proveedor = {
  id: string;
  razon_social: string | null;
  persona_id: string | null;
};

const ESTADO_INICIAL: EstadoAsiento = { error: "", ok: false };

function DialogoEjecutar({ pago, proveedor }: { pago: Pago; proveedor: string }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(ejecutarPagoAction, ESTADO_INICIAL);

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
        className="text-xs font-bold text-primary hover:underline"
      >
        Ejecutar
      </button>
      <dialog ref={dialogRef} className="w-full max-w-sm rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="movimiento_id" value={pago.id} />
          <h2 className="font-heading text-lg italic uppercase text-dark">Ejecutar pago</h2>
          <p className="text-sm text-gray">
            {proveedor} · S/ {pago.monto}
            {pago.monto_detraccion && Number(pago.monto_detraccion) > 0 && (
              <> · detracción S/ {pago.monto_detraccion}</>
            )}
          </p>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Medio de pago
            <select name="medio_pago" defaultValue="transferencia">
              <option value="transferencia">Transferencia</option>
              <option value="efectivo">Efectivo</option>
              <option value="cheque">Cheque</option>
              <option value="deposito">Depósito</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Constancia
            <input name="constancia" maxLength={255} placeholder="Nº de operación, voucher..." />
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
              {pendiente ? "Pagando..." : "Pagar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function Acciones({ pago, proveedor }: { pago: Pago; proveedor: string }) {
  const [pendiente, startTransition] = useTransition();
  if (pago.estado !== "pendiente") {
    return <span className="text-xs text-gray">{pago.medio_pago ?? "—"}</span>;
  }
  return (
    <div className="flex items-center gap-3">
      <DialogoEjecutar pago={pago} proveedor={proveedor} />
      <button
        type="button"
        disabled={pendiente}
        onClick={() => startTransition(() => void rechazarPagoAction(pago.id))}
        className="text-xs font-semibold text-secondary hover:underline"
      >
        Rechazar
      </button>
    </div>
  );
}

export function PagosCliente({
  pagos,
  proveedores,
}: {
  pagos: Pago[];
  proveedores: Proveedor[];
}) {
  const [soloPendientes, setSoloPendientes] = useState(true);
  const nombre = useMemo(
    () =>
      new Map(
        proveedores.map((p) => [p.id, p.razon_social ?? "(proveedor natural)"] as const),
      ),
    [proveedores],
  );
  const visibles = useMemo(
    () => (soloPendientes ? pagos.filter((p) => p.estado === "pendiente") : pagos),
    [pagos, soloPendientes],
  );

  const columnas: ColumnDef<Pago>[] = useMemo(
    () => [
      {
        id: "proveedor",
        header: "Proveedor",
        accessorFn: (p) =>
          (p.proveedor_id && nombre.get(p.proveedor_id)) || p.proveedor_id || "—",
      },
      { accessorKey: "concepto", header: "Concepto" },
      {
        id: "monto",
        header: "Monto",
        accessorFn: (p) => `S/ ${p.monto}`,
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          const clase =
            estado === "ejecutado"
              ? "bg-accent/30 text-dark"
              : estado === "rechazado"
                ? "bg-gray/20 text-gray"
                : "bg-secondary/15 text-secondary";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {estado}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <Acciones
            pago={row.original}
            proveedor={
              (row.original.proveedor_id && nombre.get(row.original.proveedor_id)) ||
              "Proveedor"
            }
          />
        ),
      },
    ],
    [nombre],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl italic uppercase text-dark">Pagos a proveedor</h1>
      <p className="text-sm text-gray">
        La cola la llena la conformidad del comprobante en Compras: nada entra acá sin
        haberse recibido y conformado antes. Ejecutar genera el asiento contable.
      </p>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input
          type="checkbox"
          checked={soloPendientes}
          onChange={(e) => setSoloPendientes(e.target.checked)}
        />
        Solo pendientes
      </label>
      <TablaDatos columnas={columnas} datos={visibles} placeholderBusqueda="Buscar pago..." />
    </div>
  );
}
