"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  actualizarCantidad,
  alCambiarCarrito,
  obtenerCarrito,
  totalDelCarrito,
  type LineaCarrito,
} from "@/lib/carrito";

export function CarritoCliente() {
  const [lineas, setLineas] = useState<LineaCarrito[]>([]);

  useEffect(() => {
    const actualizar = () => setLineas(obtenerCarrito());
    actualizar();
    return alCambiarCarrito(actualizar);
  }, []);

  if (lineas.length === 0) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <h1 className="font-display text-2xl uppercase text-negro">Tu carrito está vacío</h1>
        <Link href="/carta" className="mt-4 inline-block font-bold text-verde underline">
          Ver la carta
        </Link>
      </div>
    );
  }

  const total = totalDelCarrito(lineas);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <h1 className="font-display text-2xl uppercase text-negro">Tu carrito</h1>
      <ul className="flex flex-col gap-3">
        {lineas.map((l) => (
          <li
            key={l.productoComercialId}
            className="flex items-center gap-3 rounded-lg border-2 border-negro bg-white p-3"
          >
            <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded bg-crema-2">
              {l.fotoUrl && <Image src={l.fotoUrl} alt={l.nombre} fill className="object-cover" />}
            </div>
            <div className="flex-1">
              <p className="font-bold">{l.nombre}</p>
              <p className="text-sm text-humo">S/ {l.precio}</p>
            </div>
            <div className="flex items-center rounded border-2 border-negro">
              <button
                type="button"
                onClick={() => actualizarCantidad(l.productoComercialId, l.cantidad - 1)}
                className="px-2 py-1 font-bold"
                aria-label="Menos"
              >
                −
              </button>
              <span className="w-6 text-center">{l.cantidad}</span>
              <button
                type="button"
                onClick={() => actualizarCantidad(l.productoComercialId, l.cantidad + 1)}
                className="px-2 py-1 font-bold"
                aria-label="Más"
              >
                +
              </button>
            </div>
            <button
              type="button"
              onClick={() => actualizarCantidad(l.productoComercialId, 0)}
              className="text-xs text-rojo hover:underline"
            >
              Quitar
            </button>
          </li>
        ))}
      </ul>
      <div className="flex items-center justify-between border-t-2 border-negro pt-4">
        <span className="font-bold uppercase">Total</span>
        <span className="font-display text-2xl text-verde">S/ {total.toFixed(2)}</span>
      </div>
      <Link
        href="/checkout"
        className="sombra-dura rounded bg-verde px-4 py-3 text-center font-bold uppercase text-negro hover:bg-verde-hover"
      >
        Continuar
      </Link>
    </div>
  );
}
