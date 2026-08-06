"use client";

import { useActionState, useEffect, useRef, useTransition } from "react";

import { crearDivisaAction, editarDivisaAction, type EstadoGerencia } from "../actions";

export type DivisaCompleta = {
  id: string;
  codigo: string;
  nombre: string;
  simbolo: string;
  decimales: number;
  activa: boolean;
};

const ESTADO_INICIAL: EstadoGerencia = { error: "", ok: false };

function DialogoNuevaDivisa() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearDivisaAction, ESTADO_INICIAL);

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
        + Nueva divisa
      </button>
      <dialog ref={dialogRef} className="w-full max-w-sm rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nueva divisa</h2>
          <div className="flex gap-2">
            <label className="flex w-24 flex-col gap-1 text-sm font-semibold">
              Código
              <input name="codigo" required maxLength={3} minLength={3} placeholder="USD" />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Nombre
              <input name="nombre" required maxLength={50} placeholder="Dólar americano" />
            </label>
          </div>
          <div className="flex gap-2">
            <label className="flex w-24 flex-col gap-1 text-sm font-semibold">
              Símbolo
              <input name="simbolo" required maxLength={5} placeholder="$" />
            </label>
            <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
              Decimales
              <input name="decimales" type="number" min={0} max={6} defaultValue={2} />
            </label>
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

function BotonActiva({ divisa }: { divisa: DivisaCompleta }) {
  const [pendiente, startTransition] = useTransition();
  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={() =>
        startTransition(() => void editarDivisaAction(divisa.id, { activa: !divisa.activa }))
      }
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
        divisa.activa ? "bg-accent/30 text-dark" : "bg-gray/20 text-gray"
      }`}
    >
      {divisa.activa ? "Activa" : "Inactiva"}
    </button>
  );
}

export function DivisasCliente({ divisas }: { divisas: DivisaCompleta[] }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Divisas</h1>
        <DialogoNuevaDivisa />
      </div>
      <p className="text-sm text-gray">
        Toda magnitud lleva su unidad (RN-GER-010): un monto sin divisa no entra al ERP.
        Los <strong>decimales</strong> de acá deciden cómo se redondea cada importe en esa
        moneda, así que cambiarlos cambia el redondeo de todo lo que venga después.
      </p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Código</th>
            <th className="py-2 pr-4 font-semibold">Nombre</th>
            <th className="py-2 pr-4 font-semibold">Símbolo</th>
            <th className="py-2 pr-4 font-semibold">Decimales</th>
            <th className="py-2 font-semibold">Estado</th>
          </tr>
        </thead>
        <tbody>
          {divisas.map((d) => (
            <tr key={d.id} className="border-b border-gray/15">
              <td className="py-2 pr-4 font-semibold text-dark">{d.codigo}</td>
              <td className="py-2 pr-4">{d.nombre}</td>
              <td className="py-2 pr-4">{d.simbolo}</td>
              <td className="py-2 pr-4 tabular-nums">{d.decimales}</td>
              <td className="py-2">
                <BotonActiva divisa={d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
