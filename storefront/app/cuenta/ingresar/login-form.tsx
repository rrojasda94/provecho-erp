"use client";

import { useActionState } from "react";

import { ESTADO_INICIAL } from "@/lib/estado-formulario";
import { loginAction } from "../actions";

export function LoginForm() {
  const [estado, formAction, pendiente] = useActionState(loginAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2">
      <input name="email" type="email" placeholder="Email" required className="rounded border-2 border-negro px-3 py-2" />
      <input
        name="password"
        type="password"
        placeholder="Clave"
        required
        className="rounded border-2 border-negro px-3 py-2"
      />
      <button
        type="submit"
        disabled={pendiente}
        className="sombra-dura rounded bg-verde px-4 py-2 font-bold uppercase text-negro disabled:opacity-60"
      >
        {pendiente ? "Ingresando..." : "Ingresar"}
      </button>
      {estado.error && <p className="text-sm text-rojo">{estado.error}</p>}
    </form>
  );
}
