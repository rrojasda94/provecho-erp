"use client";

import { useState } from "react";

import { agregarAlCarrito } from "@/lib/carrito";

type Opcion = { id: string; nombre: string; precio: string; disponible: boolean };

export function AgregarCarrito({
  fotoUrl,
  opciones,
}: {
  fotoUrl: string | null;
  opciones: Opcion[];
}) {
  const [seleccion, setSeleccion] = useState(opciones[0]?.id ?? "");
  const [cantidad, setCantidad] = useState(1);
  const [agregado, setAgregado] = useState(false);

  const elegida = opciones.find((o) => o.id === seleccion) ?? opciones[0];
  if (!elegida) return null;

  return (
    <div className="flex flex-col gap-3 border-t-2 border-negro/10 pt-4">
      {opciones.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {opciones.map((o) => (
            <button
              key={o.id}
              type="button"
              disabled={!o.disponible}
              onClick={() => setSeleccion(o.id)}
              className={`rounded-full border-2 border-negro px-3 py-1 text-xs font-bold uppercase disabled:opacity-40 ${
                seleccion === o.id ? "bg-verde text-negro" : "bg-white"
              }`}
            >
              {o.nombre}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3">
        <div className="flex items-center rounded border-2 border-negro">
          <button
            type="button"
            onClick={() => setCantidad((c) => Math.max(1, c - 1))}
            className="px-3 py-1 font-bold"
            aria-label="Menos"
          >
            −
          </button>
          <span className="w-8 text-center">{cantidad}</span>
          <button
            type="button"
            onClick={() => setCantidad((c) => Math.min(20, c + 1))}
            className="px-3 py-1 font-bold"
            aria-label="Más"
          >
            +
          </button>
        </div>
        <button
          type="button"
          disabled={!elegida.disponible}
          onClick={() => {
            agregarAlCarrito(
              {
                productoComercialId: elegida.id,
                nombre: elegida.nombre,
                precio: elegida.precio,
                fotoUrl,
              },
              cantidad,
            );
            setAgregado(true);
            setTimeout(() => setAgregado(false), 1500);
          }}
          className="sombra-dura flex-1 rounded bg-verde px-4 py-2 font-bold uppercase text-negro hover:bg-verde-hover disabled:opacity-50"
        >
          {agregado ? "¡Agregado!" : `Agregar — S/ ${elegida.precio}`}
        </button>
      </div>
    </div>
  );
}
