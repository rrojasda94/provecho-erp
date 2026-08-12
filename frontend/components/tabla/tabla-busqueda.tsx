"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { Input } from "@/components/ui/input";

/**
 * Buscador de la tabla. Era un `<input>` nativo sin una sola clase de estilo
 * —el "parece más HTML que elementos interactivos" de ADR-035, replicado en
 * las 28 pantallas que usan la tabla.
 *
 * El atajo `/` enfoca el buscador, como en cualquier herramienta que se opera
 * ocho horas seguidas. Se ignora mientras se escribe en otro campo: una barra
 * tecleada dentro de un formulario no debe robarse el foco.
 */
export function TablaBusqueda({
  valor,
  alCambiar,
  placeholder,
}: {
  valor: string;
  alCambiar: (v: string) => void;
  placeholder: string;
}) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function alTeclear(e: KeyboardEvent) {
      const activo = document.activeElement?.tagName;
      if (e.key !== "/" || activo === "INPUT" || activo === "TEXTAREA") return;
      e.preventDefault();
      ref.current?.focus();
    }
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, []);

  return (
    <div className="relative mb-3 max-w-xs">
      <Search
        size={14}
        strokeWidth={2}
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        ref={ref}
        value={valor}
        onChange={(e) => alCambiar(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="pr-7 pl-7"
      />
      {valor && (
        <button
          type="button"
          aria-label="Limpiar búsqueda"
          onClick={() => alCambiar("")}
          className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded-sm p-0.5 text-muted-foreground hover:text-foreground"
        >
          <X size={13} strokeWidth={2.25} aria-hidden />
        </button>
      )}
    </div>
  );
}
