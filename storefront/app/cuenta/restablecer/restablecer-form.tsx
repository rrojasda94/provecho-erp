"use client";

import { useActionState } from "react";

import { Boton } from "@/components/boton";
import { CampoClave } from "@/components/campo-clave";
import { ESTADO_INICIAL } from "@/lib/estado-formulario";

import { restablecerClaveAction } from "../actions";

export function RestablecerForm({ token }: { token: string }) {
  const [estado, formAction] = useActionState(restablecerClaveAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2">
      <input type="hidden" name="token" value={token} />
      <CampoClave
        name="password"
        placeholder="Clave nueva (mínimo 8 caracteres)"
        minLength={8}
        required
        autoComplete="new-password"
      />
      <CampoClave
        name="confirmar"
        placeholder="Repite la clave nueva"
        minLength={8}
        required
        autoComplete="new-password"
      />
      <Boton esperando="Guardando...">Cambiar mi clave</Boton>
      {estado.error && (
        <p role="alert" className="text-sm text-rojo">
          {estado.error}
        </p>
      )}
    </form>
  );
}
