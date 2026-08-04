"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { anularAsientoAction, crearAsientoAction, type EstadoAsiento } from "./actions";

export type Asiento = {
  id: string;
  fecha: string;
  glosa: string;
  origen: string;
  evento_origen: string | null;
  estado: string;
  asiento_reversa_de_id: string | null;
};
export type Cuenta = {
  id: string;
  codigo: string;
  nombre: string;
  tipo: string;
  activa: boolean;
};

const ESTADO_INICIAL: EstadoAsiento = { error: "", ok: false };

type LineaForm = { clave: number; cuenta: string; tipo: "debe" | "haber"; monto: string };

const LINEAS_INICIALES: LineaForm[] = [
  { clave: 1, cuenta: "", tipo: "debe", monto: "" },
  { clave: 2, cuenta: "", tipo: "haber", monto: "" },
];

function total(lineas: LineaForm[], tipo: "debe" | "haber"): number {
  return lineas
    .filter((l) => l.tipo === tipo)
    .reduce((t, l) => t + (Number(l.monto) || 0), 0);
}

function DialogoNuevoAsiento({ cuentas }: { cuentas: Cuenta[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [lineas, setLineas] = useState<LineaForm[]>(LINEAS_INICIALES);
  const [estado, formAction, pendiente] = useActionState(crearAsientoAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      setLineas(LINEAS_INICIALES);
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  const debe = total(lineas, "debe");
  const haber = total(lineas, "haber");
  const cuadra = debe > 0 && debe === haber;

  const editar = (clave: number, campo: keyof LineaForm, valor: string) =>
    setLineas((prev) =>
      prev.map((l) => (l.clave === clave ? { ...l, [campo]: valor } : l)),
    );

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Asiento manual
      </button>
      <dialog ref={dialogRef} className="w-full max-w-2xl rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Asiento manual</h2>
          <div className="flex gap-4">
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Fecha
              <input name="fecha" type="date" required />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Glosa
              <input name="glosa" required maxLength={255} placeholder="Qué documenta el asiento" />
            </label>
          </div>

          <div className="flex flex-col gap-2">
            {lineas.map((linea) => (
              <div key={linea.clave} className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
                  Cuenta
                  <select
                    name="cuenta_contable_id"
                    required
                    value={linea.cuenta}
                    onChange={(e) => editar(linea.clave, "cuenta", e.target.value)}
                    className="rounded border border-gray/40 px-2 py-1 text-sm"
                  >
                    <option value="" disabled>
                      Elegir cuenta...
                    </option>
                    {cuentas
                      .filter((c) => c.activa)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.codigo} · {c.nombre}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="flex w-28 flex-col gap-1 text-xs font-semibold">
                  Tipo
                  <select
                    name="tipo"
                    value={linea.tipo}
                    onChange={(e) => editar(linea.clave, "tipo", e.target.value)}
                    className="rounded border border-gray/40 px-2 py-1 text-sm"
                  >
                    <option value="debe">Debe</option>
                    <option value="haber">Haber</option>
                  </select>
                </label>
                <label className="flex w-32 flex-col gap-1 text-xs font-semibold">
                  Monto
                  <input
                    name="monto"
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={linea.monto}
                    onChange={(e) => editar(linea.clave, "monto", e.target.value)}
                    className="rounded border border-gray/40 px-2 py-1 text-sm"
                  />
                </label>
                <button
                  type="button"
                  aria-label="Quitar línea"
                  disabled={lineas.length <= 2}
                  onClick={() =>
                    setLineas((prev) => prev.filter((l) => l.clave !== linea.clave))
                  }
                  className="pb-1.5 text-gray hover:text-secondary disabled:opacity-30"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                setLineas((prev) => [
                  ...prev,
                  { clave: Math.max(...prev.map((l) => l.clave)) + 1, cuenta: "", tipo: "debe", monto: "" },
                ])
              }
              className="self-start text-sm font-semibold text-primary hover:underline"
            >
              + Agregar línea
            </button>
          </div>

          {/* El cuadre en vivo (RN-CTB-001): el error más común es tipear un
              monto de más, y verlo antes de enviar ahorra el viaje. */}
          <div
            className={`flex justify-end gap-6 rounded px-3 py-2 text-sm font-semibold ${
              cuadra ? "bg-accent/20 text-dark" : "bg-secondary/10 text-secondary"
            }`}
          >
            <span>Debe: {debe.toFixed(2)}</span>
            <span>Haber: {haber.toFixed(2)}</span>
            <span>{cuadra ? "Cuadra" : `Diferencia: ${(debe - haber).toFixed(2)}`}</span>
          </div>

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
              disabled={pendiente || !cuadra}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-40"
            >
              {pendiente ? "Registrando..." : "Registrar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function BotonAnular({ asiento }: { asiento: Asiento }) {
  const [pendiente, startTransition] = useTransition();
  if (asiento.estado !== "registrado") return <span className="text-xs text-gray">—</span>;
  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={() => startTransition(() => void anularAsientoAction(asiento.id))}
      title="Genera el asiento inverso (RN-CTB-002): nada se borra"
      className="text-xs font-semibold text-secondary hover:underline"
    >
      Anular
    </button>
  );
}

export function AsientosCliente({
  asientos,
  cuentas,
}: {
  asientos: Asiento[];
  cuentas: Cuenta[];
}) {
  const columnas: ColumnDef<Asiento>[] = useMemo(
    () => [
      { accessorKey: "fecha", header: "Fecha" },
      { accessorKey: "glosa", header: "Glosa" },
      {
        id: "origen",
        header: "Origen",
        accessorFn: (a) => (a.origen === "automatico" ? (a.evento_origen ?? "automático") : "manual"),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          return (
            <span
              className={
                estado === "anulado"
                  ? "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
                  : "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
              }
            >
              {estado}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <BotonAnular asiento={row.original} />,
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Asientos</h1>
        <DialogoNuevoAsiento cuentas={cuentas} />
      </div>
      <p className="text-sm text-gray">
        El libro. Los asientos automáticos los genera un evento del ERP (venta, compra,
        pago); los manuales se registran acá y siempre cuadran debe contra haber.
      </p>
      {cuentas.length === 0 && (
        <p className="rounded bg-secondary/10 px-3 py-2 text-sm font-semibold text-secondary">
          No hay plan de cuentas todavía: sin cuentas no se puede registrar un asiento.
        </p>
      )}
      <TablaDatos columnas={columnas} datos={asientos} placeholderBusqueda="Buscar por glosa..." />
    </div>
  );
}
