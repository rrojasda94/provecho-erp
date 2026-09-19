"use client";

import { useActionState } from "react";

import { ESTADO_INICIAL } from "@/lib/estado-formulario";

import { cambiarClaveAction } from "../actions";

export function CambiarClaveForm({ pideActual }: { pideActual: boolean }) {
  const [estado, formAction, pendiente] = useActionState(cambiarClaveAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2">
      {pideActual && (
        <input
          name="clave_actual"
          type="password"
          placeholder="Clave actual"
          required
          autoComplete="current-password"
          className="rounded border-2 border-negro px-3 py-2"
        />
      )}
      <input
        name="clave_nueva"
        type="password"
        placeholder="Clave nueva (mínimo 8 caracteres)"
        minLength={8}
        required
        autoComplete="new-password"
        className="rounded border-2 border-negro px-3 py-2"
      />
      <input
        name="confirmar"
        type="password"
        placeholder="Repite la clave nueva"
        minLength={8}
        required
        autoComplete="new-password"
        className="rounded border-2 border-negro px-3 py-2"
      />
      <button type="submit" disabled={pendiente} className="sombra-dura rounded bg-verde px-4 py-2 font-bold uppercase text-negro disabled:opacity-60">
        {pendiente ? "Guardando..." : "Guardar mi clave"}
      </button>
      {estado.error && <p className="text-sm text-rojo">{estado.error}</p>}
    </form>
  );
}
