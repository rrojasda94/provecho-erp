"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import type { Falla } from "@/lib/carga";

/**
 * Lo que una pantalla **no pudo** traer, con el reintento a mano.
 *
 * Existe para que un bloque caído no se confunda con un bloque vacío ni con
 * uno que el usuario no tiene permiso de ver: el 403 se filtra antes de
 * llegar acá (ver `esSinPermiso` en `lib/carga.ts`), así que todo lo que
 * este componente muestra es algo que puede salir bien al reintentar.
 *
 * Las pantallas del shell se arman en el servidor, así que "reintentar" es
 * pedirle a Next que vuelva a renderizar (`router.refresh()`), no un fetch
 * suelto que la página no sabría dónde poner. Va en una transición para
 * poder deshabilitar el botón mientras tanto: sin eso, tres toques
 * impacientes son tres renders del servidor.
 *
 * El detalle técnico se muestra a propósito. Un aviso que solo dice "algo
 * falló" obliga a abrir las herramientas de desarrollo para saber qué —
 * justo lo que no se puede pedir en un mostrador.
 */
export function AvisoFallo({ fallas }: { fallas: Falla[] }) {
  const router = useRouter();
  const [reintentando, empezar] = useTransition();

  if (fallas.length === 0) return null;

  return (
    <section
      role="alert"
      className="rounded border border-secondary/40 bg-secondary/5 p-4 text-sm"
    >
      <ul className="flex flex-col gap-1">
        {fallas.map((f, i) => (
          <li key={`${f.mensaje}-${i}`}>
            <span className="font-semibold text-secondary">{f.mensaje}</span>{" "}
            <span className="text-xs text-gray">
              {f.status ? `Error ${f.status}` : "Sin respuesta del servidor"}
              {f.detalle ? ` · ${f.detalle}` : ""}
            </span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        disabled={reintentando}
        onClick={() => empezar(() => router.refresh())}
        className="mt-3 rounded border border-secondary/40 px-3 py-1.5 text-xs font-semibold text-secondary disabled:opacity-50"
      >
        {reintentando ? "Reintentando…" : "Reintentar"}
      </button>
    </section>
  );
}
