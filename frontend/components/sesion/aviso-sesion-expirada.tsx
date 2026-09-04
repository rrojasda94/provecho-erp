"use client";

import { useEffect, useRef, useState } from "react";

import { estaMuerta, suscribir } from "@/lib/sesion-muerta";

/**
 * La única salida cuando la sesión del navegador ya no vale.
 *
 * Hasta hoy no había ninguna. Lo que hacía cada pantalla con su 401 era, en
 * los tres casos, no decirlo: el KDS lo mostraba cuatro segundos y seguía
 * refrescando cada tres —la cola de cocina quedaba congelada en el último
 * dato bueno—, la campana lo tragaba con un `catch {}` y mostraba el conteo
 * viejo, y el PDV lo tragaba también y dejaba de persistir el borrador sin
 * ninguna señal: el cajero se enteraba al recargar, con las pestañas vacías.
 *
 * Va en el layout raíz porque el problema no es de un módulo: alcanza a
 * `(app)`, a `/pdv` y a `/kds`, que son tres árboles distintos. Y es un
 * `<dialog>` modal —no un banner— por lo mismo que `pdv/bloqueo.tsx`: lo que
 * hay detrás ya no se puede operar, y un aviso esquivable en una tablet de
 * cocina se esquiva.
 */
export function AvisoSesionExpirada() {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Puede haber muerto antes de que este efecto corra: el PDV dispara su
    // primer fetch en el mismo tick en que monta.
    if (estaMuerta()) setVisible(true);
    return suscribir(() => setVisible(true));
  }, []);

  useEffect(() => {
    if (visible) dialogo.current?.showModal();
  }, [visible]);

  if (!visible) return null;

  return (
    <dialog
      ref={dialogo}
      aria-labelledby="sesion-expirada-titulo"
      // Escape no lo cierra: no hay nada que hacer atrás, y cerrarlo dejaría
      // una pantalla que parece viva y no lo está.
      onCancel={(e) => e.preventDefault()}
      className="w-full max-w-sm rounded-xl border border-border bg-card p-0 text-card-foreground shadow-[var(--sombra-3)] backdrop:bg-dark/50"
    >
      <div className="flex flex-col gap-3 p-5">
        <h2 id="sesion-expirada-titulo" className="text-base leading-tight">
          Tu sesión expiró
        </h2>
        <p className="text-sm text-muted-foreground">
          Por seguridad la sesión se cierra sola tras un rato sin actividad
          (ADR-084). Lo que está en pantalla es lo último que se pudo traer:
          ya no se está actualizando.
        </p>
        <button
          type="button"
          onClick={() => {
            window.location.href = "/login";
          }}
          className="inline-flex items-center justify-center rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85"
        >
          Volver a entrar
        </button>
      </div>
    </dialog>
  );
}
