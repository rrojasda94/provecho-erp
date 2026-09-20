"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { Boton } from "@/components/boton";
import { CampoClave } from "@/components/campo-clave";
import { ESTADO_INICIAL } from "@/lib/estado-formulario";
import { loginAction } from "../actions";

export function LoginForm() {
  const [estado, formAction] = useActionState(loginAction, ESTADO_INICIAL);
  // Controlados a propósito: React 19 resetea el `<form>` cuando la acción
  // termina, así que con campos no controlados un error de clave borraba
  // también el correo y obligaba a escribir todo de nuevo. El valor vive en el
  // navegador; la clave nunca vuelve desde el servidor.
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");

  return (
    <form action={formAction} className="flex flex-col gap-2">
      <input
        name="email"
        type="email"
        placeholder="Email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="rounded border-2 border-negro px-3 py-2"
      />
      <CampoClave
        name="password"
        placeholder="Clave"
        required
        autoComplete="current-password"
        value={clave}
        onChange={(e) => setClave(e.target.value)}
      />
      <Boton esperando="Ingresando...">Ingresar</Boton>
      {estado.error && (
        <p role="alert" className="text-sm text-rojo">
          {estado.error}
        </p>
      )}
      <Link href="/cuenta/recuperar" className="text-center text-xs text-humo underline">
        ¿Olvidaste tu contraseña?
      </Link>
    </form>
  );
}
