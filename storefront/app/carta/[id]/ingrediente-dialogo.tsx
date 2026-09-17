"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";

export type IngredienteDetalle = {
  id: string;
  nombre: string;
  descripcion: string | null;
  foto_url: string | null;
};

/**
 * `<dialog>` nativo (sin librería) — mismo patrón que el back office
 * (`docs/product/ui-ux.md` §Movimiento 5): `::backdrop` con blur y el panel
 * entra con una animación de solo-entrada (`backwards`, ver `globals.css`),
 * porque animar la salida de un `<dialog>` nativo exige
 * `@starting-style`/`transition-behavior: allow-discrete` y acá no compensa.
 */
export function IngredienteDialogo({
  ingrediente,
  onCerrar,
}: {
  ingrediente: IngredienteDetalle | null;
  onCerrar: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialogo = ref.current;
    if (!dialogo) return;
    if (ingrediente && !dialogo.open) dialogo.showModal();
    if (!ingrediente && dialogo.open) dialogo.close();
  }, [ingrediente]);

  return (
    <dialog
      ref={ref}
      onClose={onCerrar}
      onClick={(e) => {
        if (e.target === ref.current) onCerrar();
      }}
      className="w-full max-w-sm rounded-lg border-2 border-negro bg-white p-0 backdrop:bg-transparent"
    >
      {ingrediente && (
        <div className="flex flex-col">
          {ingrediente.foto_url && (
            <div className="relative h-40 w-full">
              <Image src={ingrediente.foto_url} alt={ingrediente.nombre} fill className="object-cover" />
            </div>
          )}
          <div className="flex flex-col gap-2 p-4">
            <div className="flex items-start justify-between">
              <h3 className="font-display text-xl uppercase text-negro">{ingrediente.nombre}</h3>
              <button
                type="button"
                onClick={onCerrar}
                aria-label="Cerrar"
                className="text-lg font-bold text-humo hover:text-negro"
              >
                ×
              </button>
            </div>
            <p className="text-sm text-humo">
              {ingrediente.descripcion ?? "Uno de los ingredientes de esta pizza."}
            </p>
          </div>
        </div>
      )}
    </dialog>
  );
}
