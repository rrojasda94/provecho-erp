"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { alCambiarCarrito, cantidadTotal, obtenerCarrito } from "@/lib/carrito";

export function CarritoBadge() {
  const [cantidad, setCantidad] = useState(0);

  useEffect(() => {
    const actualizar = () => setCantidad(cantidadTotal(obtenerCarrito()));
    actualizar();
    return alCambiarCarrito(actualizar);
  }, []);

  return (
    <Link href="/carrito" className="relative flex items-center gap-1 hover:text-verde">
      Carrito
      {cantidad > 0 && (
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-rojo px-1 text-xs font-bold text-white">
          {cantidad}
        </span>
      )}
    </Link>
  );
}
