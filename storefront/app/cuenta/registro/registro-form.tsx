"use client";

import { useActionState } from "react";

import { ESTADO_INICIAL } from "@/lib/estado-formulario";
import { registrarAction } from "../actions";

const CAMPO = "rounded border-2 border-negro px-3 py-2";

export function RegistroForm() {
  const [estado, formAction, pendiente] = useActionState(registrarAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input name="nombres" placeholder="Nombres" required className={CAMPO + " flex-1"} />
        <input name="apellidos" placeholder="Apellidos" required className={CAMPO + " flex-1"} />
      </div>
      <input name="email" type="email" placeholder="Email" required className={CAMPO} />
      <input
        name="password"
        type="password"
        placeholder="Clave (mínimo 8 caracteres)"
        required
        minLength={8}
        className={CAMPO}
      />
      <div className="flex gap-2">
        <input name="numero_documento" placeholder="DNI" required maxLength={15} className={CAMPO + " flex-1"} />
        <input name="telefono" placeholder="Teléfono" required maxLength={20} className={CAMPO + " flex-1"} />
      </div>
      <label className="text-xs text-humo">
        Fecha de nacimiento
        <input name="fecha_nacimiento" type="date" required className={CAMPO + " w-full"} />
      </label>
      <input name="direccion" placeholder="Dirección (opcional)" className={CAMPO} />
      <button
        type="submit"
        disabled={pendiente}
        className="sombra-dura rounded bg-verde px-4 py-2 font-bold uppercase text-negro disabled:opacity-60"
      >
        {pendiente ? "Creando..." : "Crear cuenta"}
      </button>
      {estado.error && <p className="text-sm text-rojo">{estado.error}</p>}
    </form>
  );
}
