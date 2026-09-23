"use client";

import { useActionState, useState } from "react";

import { Boton } from "@/components/boton";
import { CampoClave } from "@/components/campo-clave";
import { ESTADO_INICIAL } from "@/lib/estado-formulario";
import { registrarAction } from "../actions";

const CAMPO = "rounded border-2 border-negro px-3 py-2";

export function RegistroForm() {
  const [estado, formAction] = useActionState(registrarAction, ESTADO_INICIAL);
  // Un solo estado para los ocho campos: React 19 vacía el formulario cuando
  // la acción termina, y rellenar todo de nuevo porque el DNI ya existía es
  // el tipo de castigo que hace abandonar un registro.
  const [valores, setValores] = useState<Record<string, string>>({});
  const campo = (name: string) => ({
    name,
    value: valores[name] ?? "",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setValores((v) => ({ ...v, [name]: e.target.value })),
  });

  return (
    <form action={formAction} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          {...campo("nombres")}
          placeholder="Nombres"
          required
          autoComplete="given-name"
          className={CAMPO + " flex-1"}
        />
        <input
          {...campo("apellidos")}
          placeholder="Apellidos"
          required
          autoComplete="family-name"
          className={CAMPO + " flex-1"}
        />
      </div>
      <input
        {...campo("email")}
        type="email"
        placeholder="Email"
        required
        autoComplete="email"
        className={CAMPO}
      />
      <CampoClave
        {...campo("password")}
        placeholder="Clave (mínimo 8 caracteres)"
        required
        minLength={8}
        autoComplete="new-password"
      />
      <div className="flex gap-2">
        <input
          {...campo("numero_documento")}
          placeholder="DNI"
          required
          maxLength={15}
          inputMode="numeric"
          className={CAMPO + " flex-1"}
        />
        <input
          {...campo("telefono")}
          placeholder="Teléfono"
          required
          maxLength={20}
          inputMode="tel"
          autoComplete="tel"
          className={CAMPO + " flex-1"}
        />
      </div>
      <label className="text-xs text-humo">
        Fecha de nacimiento
        <input
          {...campo("fecha_nacimiento")}
          type="date"
          required
          className={CAMPO + " w-full"}
        />
      </label>
      <input {...campo("direccion")} placeholder="Dirección (opcional)" className={CAMPO} />
      <Boton esperando="Creando...">Crear cuenta</Boton>
      {estado.error && (
        <p role="alert" className="text-sm text-rojo">
          {estado.error}
        </p>
      )}
    </form>
  );
}
