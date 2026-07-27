"use client";

import { useActionState } from "react";

import { loginAction, type EstadoLogin } from "./actions";

const ESTADO_INICIAL: EstadoLogin = { error: "" };

export default function LoginPage() {
  const [estado, formAction, pendiente] = useActionState(loginAction, ESTADO_INICIAL);

  return (
    <main className="login-page">
      <div className="login-card">
        <h1>Provecho</h1>
        <p className="login-tagline">¿Qué se te antoja hoy?</p>
        <form action={formAction} className="login-form">
          <label>
            Usuario
            <input name="username" autoComplete="username" required autoFocus />
          </label>
          <label>
            PIN
            <input
              name="pin"
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              autoComplete="current-password"
              required
            />
          </label>
          {estado.error && (
            <p className="login-error" role="alert">
              {estado.error}
            </p>
          )}
          <button type="submit" disabled={pendiente}>
            {pendiente ? "Ingresando..." : "Ingresar"}
          </button>
        </form>
      </div>
    </main>
  );
}
