"use client";

import { useActionState } from "react";

import { Boton } from "@/components/boton";
import { CampoClave } from "@/components/campo-clave";
import { ESTADO_INICIAL } from "@/lib/estado-formulario";

import { cambiarClaveAction } from "../actions";

export function CambiarClaveForm({ pideActual }: { pideActual: boolean }) {
  const [estado, formAction] = useActionState(cambiarClaveAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2">
      {pideActual && (
        <CampoClave
          name="clave_actual"
          placeholder="Clave actual"
          required
          autoComplete="current-password"
        />
      )}
      <CampoClave
        name="clave_nueva"
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
      <Boton esperando="Guardando...">Guardar mi clave</Boton>
      {estado.error && (
        <p role="alert" className="text-sm text-rojo">
          {estado.error}
        </p>
      )}
    </form>
  );
}
