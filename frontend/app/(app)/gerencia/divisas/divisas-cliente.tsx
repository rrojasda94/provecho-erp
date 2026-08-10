"use client";

import { useTransition } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";

import { crearDivisaAction, editarDivisaAction, guardarDivisaAction } from "../actions";

export type DivisaCompleta = {
  id: string;
  codigo: string;
  nombre: string;
  simbolo: string;
  decimales: number;
  activa: boolean;
};

function DialogoNuevaDivisa() {
  return (
    <DialogoFormulario
      titulo="Nueva divisa"
      disparador="+ Nueva divisa"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearDivisaAction}
    >
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
    </DialogoFormulario>
  );
}

/** El código ISO no se edita: es la identidad de la moneda y lo que otros
 * módulos guardaron junto a cada importe. Corregirlo sería crear otra. */
function DialogoEditarDivisa({ divisa }: { divisa: DivisaCompleta }) {
  return (
    <DialogoFormulario
      titulo={`Editar ${divisa.codigo}`}
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarDivisaAction}
      ayuda="Cambiar los decimales cambia el redondeo de todo importe que venga después en esta moneda — no reescribe los ya registrados."
    >
      <input type="hidden" name="id" value={divisa.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={50} defaultValue={divisa.nombre} />
      </label>
      <div className="flex gap-2">
        <label className="flex w-24 flex-col gap-1 text-sm font-semibold">
          Símbolo
          <input name="simbolo" required maxLength={5} defaultValue={divisa.simbolo} />
        </label>
        <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
          Decimales
          <input
            name="decimales"
            type="number"
            min={0}
            max={6}
            defaultValue={divisa.decimales}
          />
        </label>
      </div>
    </DialogoFormulario>
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
            <th className="py-2 pr-4 font-semibold">Estado</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {divisas.map((d) => (
            <tr key={d.id} className="border-b border-gray/15">
              <td className="py-2 pr-4 font-semibold text-dark">{d.codigo}</td>
              <td className="py-2 pr-4">{d.nombre}</td>
              <td className="py-2 pr-4">{d.simbolo}</td>
              <td className="py-2 pr-4 tabular-nums">{d.decimales}</td>
              <td className="py-2 pr-4">
                <BotonActiva divisa={d} />
              </td>
              <td className="py-2">
                <DialogoEditarDivisa divisa={d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
