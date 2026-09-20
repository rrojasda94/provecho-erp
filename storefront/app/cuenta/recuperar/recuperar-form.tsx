"use client";

import { useActionState } from "react";

import { Boton } from "@/components/boton";
import { ESTADO_INICIAL } from "@/lib/estado-formulario";

import { recuperarClaveAction } from "../actions";

export function RecuperarForm() {
  const [estado, formAction] = useActionState(recuperarClaveAction, ESTADO_INICIAL);
  if (estado.ok) {
    return (
      <p className="rounded border-2 border-verde bg-crema-2 px-3 py-2 text-sm">
        Si ese correo tiene una cuenta, te acabamos de mandar un enlace para elegir una clave
        nueva. Vale por 30 minutos; revisa también la carpeta de spam.
      </p>
    );
  }
  return (
    <form action={formAction} className="flex flex-col gap-2">
      <input
        name="email"
        type="email"
        placeholder="Tu email"
        required
        autoComplete="email"
        className="rounded border-2 border-negro px-3 py-2"
      />
      <Boton esperando="Enviando...">Enviarme el enlace</Boton>
      {estado.error && (
        <p role="alert" className="text-sm text-rojo">
          {estado.error}
        </p>
      )}
    </form>
  );
}
