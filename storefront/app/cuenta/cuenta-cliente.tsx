"use client";

import Link from "next/link";
import { useActionState, useTransition } from "react";

import { ESTADO_INICIAL } from "@/lib/estado-formulario";

import {
  agregarDireccionAction,
  borrarDireccionAction,
  logoutAction,
} from "./actions";

export type Perfil = {
  nombres: string;
  apellidos: string;
  email: string;
  telefono: string | null;
};

export type Direccion = {
  id: string;
  etiqueta: string | null;
  direccion: string;
  referencia: string | null;
  predeterminada: boolean;
};

export type UltimoPedido = {
  numero_orden: number;
  fecha_orden: string;
  estado: string;
  total: string;
  items: { nombre: string; cantidad: string }[];
} | null;

function FormNuevaDireccion() {
  const [estado, formAction, pendiente] = useActionState(agregarDireccionAction, ESTADO_INICIAL);
  return (
    <form action={formAction} className="flex flex-col gap-2 rounded border-2 border-negro/30 p-3">
      <div className="flex gap-2">
        <input name="etiqueta" placeholder="Nombre (ej. Casa)" className="flex-1 rounded border px-2 py-1 text-sm" />
        <label className="flex items-center gap-1 text-xs">
          <input type="checkbox" name="predeterminada" /> Predeterminada
        </label>
      </div>
      <input name="direccion" placeholder="Dirección" required className="rounded border px-2 py-1 text-sm" />
      <input name="referencia" placeholder="Referencia (opcional)" className="rounded border px-2 py-1 text-sm" />
      <button
        type="submit"
        disabled={pendiente}
        className="self-start rounded bg-verde px-3 py-1 text-xs font-bold text-negro disabled:opacity-60"
      >
        {pendiente ? "Guardando..." : "Agregar dirección"}
      </button>
      {estado.error && <p className="text-xs text-rojo">{estado.error}</p>}
    </form>
  );
}

function FilaDireccion({ direccion }: { direccion: Direccion }) {
  const [pendiente, startTransition] = useTransition();
  return (
    <li className="flex items-center justify-between rounded border border-negro/20 px-3 py-2 text-sm">
      <div>
        <span className="font-semibold">{direccion.etiqueta ?? "Dirección"}</span>
        {direccion.predeterminada && (
          <span className="ml-2 rounded-full bg-verde px-2 py-0.5 text-xs">Predeterminada</span>
        )}
        <p className="text-xs text-humo">{direccion.direccion}</p>
      </div>
      <button
        type="button"
        disabled={pendiente}
        onClick={() => startTransition(() => void borrarDireccionAction(direccion.id))}
        className="text-xs text-rojo hover:underline"
      >
        Quitar
      </button>
    </li>
  );
}

export function CuentaCliente({
  perfil,
  direcciones,
  favoritosIds,
  ultimoPedido,
}: {
  perfil: Perfil;
  direcciones: Direccion[];
  favoritosIds: string[];
  ultimoPedido: UltimoPedido;
}) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl uppercase text-negro">
            Hola, {perfil.nombres}
          </h1>
          <p className="text-sm text-humo">{perfil.email}</p>
        </div>
        <form action={logoutAction}>
          <button type="submit" className="text-sm font-bold text-rojo hover:underline">
            Cerrar sesión
          </button>
        </form>
      </div>

      {ultimoPedido && (
        <section>
          <h2 className="font-display text-lg uppercase text-negro">Tu último pedido</h2>
          <div className="mt-2 rounded-lg border-2 border-negro bg-white p-4 text-sm">
            <p className="font-semibold">
              Pedido #{ultimoPedido.numero_orden} — {ultimoPedido.estado}
            </p>
            <ul className="mt-1 text-humo">
              {ultimoPedido.items.map((it, i) => (
                <li key={i}>
                  {it.cantidad}x {it.nombre}
                </li>
              ))}
            </ul>
            <p className="mt-1 font-display text-verde">Total S/ {ultimoPedido.total}</p>
          </div>
        </section>
      )}

      <section>
        <h2 className="font-display text-lg uppercase text-negro">Tus direcciones</h2>
        <ul className="mt-2 flex flex-col gap-2">
          {direcciones.map((d) => (
            <FilaDireccion key={d.id} direccion={d} />
          ))}
        </ul>
        <div className="mt-3">
          <FormNuevaDireccion />
        </div>
      </section>

      <section>
        <h2 className="font-display text-lg uppercase text-negro">
          Favoritos ({favoritosIds.length})
        </h2>
        <p className="text-sm text-humo">
          Márcalos con el corazón desde la carta.{" "}
          <Link href="/carta" className="underline">
            Ver la carta
          </Link>
        </p>
      </section>
    </div>
  );
}
