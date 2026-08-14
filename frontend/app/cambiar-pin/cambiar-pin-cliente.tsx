"use client";

import { useRouter } from "next/navigation";
import { useActionState, useEffect } from "react";

import { ESTADO_INICIAL } from "@/components/formulario/dialogo-formulario";

import { cambiarPinPropioAction } from "./actions";

const CAMPO = "rounded border border-gray/40 px-2 py-1.5 text-sm";

export function CambiarPinCliente({ username }: { username: string }) {
  const router = useRouter();
  const [estado, formAction, pendiente] = useActionState(
    cambiarPinPropioAction,
    ESTADO_INICIAL,
  );

  useEffect(() => {
    // Al inicio y no a la pantalla anterior: si se llegó acá por un reseteo,
    // la anterior era un 403.
    if (estado.ok) router.push("/");
  }, [estado.ok, router]);

  return (
    <section className="mx-auto flex max-w-sm flex-col gap-4 py-10">
      <h1 className="font-heading text-xl text-dark">Elige un PIN nuevo</h1>
      <p className="text-sm text-gray">
        Si te lo resetearon, tu PIN es <strong>123456</strong> y lo sabe quien
        te lo reseteó: hasta que elijas otro, tu cuenta no puede hacer nada
        más que esto.
      </p>

      <form action={formAction} className="flex flex-col gap-3">
        <input type="hidden" name="username" value={username} autoComplete="username" />
        <label className="flex flex-col gap-1 text-sm font-semibold">
          PIN actual
          <input
            name="pin_actual"
            type="password"
            required
            inputMode="numeric"
            maxLength={6}
            autoComplete="current-password"
            className={CAMPO}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          PIN nuevo
          <input
            name="pin_nuevo"
            type="password"
            required
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            autoComplete="new-password"
            className={CAMPO}
          />
          <span className="text-xs font-normal text-gray">
            Seis dígitos, y distinto del que viene por defecto.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Repite el PIN nuevo
          <input
            name="pin_repetido"
            type="password"
            required
            inputMode="numeric"
            maxLength={6}
            autoComplete="new-password"
            className={CAMPO}
          />
        </label>

        {estado.error && (
          <p role="alert" className="text-sm font-semibold text-secondary">
            {estado.error}
          </p>
        )}

        <button
          type="submit"
          disabled={pendiente}
          className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
        >
          {pendiente ? "Guardando..." : "Cambiar PIN"}
        </button>
      </form>
    </section>
  );
}
