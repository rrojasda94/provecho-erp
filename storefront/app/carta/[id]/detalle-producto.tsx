"use client";

import Image from "next/image";
import { useState } from "react";

import { AgregarCarrito } from "@/components/agregar-carrito";
import type { Opciones } from "@/lib/opciones";

import { IngredienteDialogo, type IngredienteDetalle } from "./ingrediente-dialogo";

type Variante = Partial<Opciones> & {
  id: string;
  nombre: string;
  precio: string;
  disponible: boolean;
};
type ProductoDetalle = Partial<Opciones> & {
  id: string;
  nombre: string;
  descripcion: string | null;
  precio_desde: string;
  disponible: boolean;
  fotos: string[];
  variantes: Variante[];
  ingredientes_detalle: IngredienteDetalle[];
};

/** La API manda las opciones siempre, pero un producto viejo en caché podría no
 * traerlas: sin ellas se vende como antes. */
const conOpciones = (o: Partial<Opciones>) => ({
  extras: o.extras ?? [],
  atributos: o.atributos ?? [],
  exclusiones: o.exclusiones ?? [],
});

export function DetalleProducto({ producto }: { producto: ProductoDetalle }) {
  const [ingredienteAbierto, setIngredienteAbierto] = useState<IngredienteDetalle | null>(null);
  const foto = producto.fotos[0];

  return (
    <div className="mx-auto grid max-w-4xl grid-cols-1 gap-8 px-4 py-8 sm:grid-cols-2">
      <div className="relative h-64 overflow-hidden rounded-lg border-2 border-negro bg-crema-2 sm:h-full">
        {foto && <Image src={foto} alt={producto.nombre} fill className="object-cover" />}
        {!producto.disponible && (
          <span className="absolute left-3 top-3 rounded bg-rojo px-2 py-1 text-xs font-bold text-white">
            No disponible ahora
          </span>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <h1 className="font-display text-3xl uppercase text-negro">{producto.nombre}</h1>
        {producto.descripcion && <p className="text-humo">{producto.descripcion}</p>}

        {producto.ingredientes_detalle.length > 0 && (
          <div>
            <h2 className="text-sm font-bold uppercase text-negro">Ingredientes</h2>
            <p className="mb-2 text-xs text-humo">Toca un ingrediente para saber más.</p>
            <div className="flex flex-wrap gap-2">
              {producto.ingredientes_detalle.map((ing) => (
                <button
                  key={ing.id}
                  type="button"
                  onClick={() => setIngredienteAbierto(ing)}
                  className="rounded-full border-2 border-negro bg-crema-2 px-3 py-1 text-xs font-semibold hover:bg-verde hover:text-white"
                >
                  {ing.nombre}
                </button>
              ))}
            </div>
          </div>
        )}

        {producto.variantes.length > 0 ? (
          <div>
            <h2 className="text-sm font-bold uppercase text-negro">Tamaños</h2>
            <ul className="mt-2 flex flex-col gap-1">
              {producto.variantes.map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between rounded border border-negro/20 px-3 py-2 text-sm"
                >
                  <span>
                    {v.nombre}
                    {!v.disponible && <span className="ml-2 text-xs text-rojo">no disponible</span>}
                  </span>
                  <span className="font-display text-verde">S/ {v.precio}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="font-display text-2xl text-verde">S/ {producto.precio_desde}</p>
        )}

        <AgregarCarrito
          fotoUrl={foto ?? null}
          opciones={
            producto.variantes.length > 0
              ? producto.variantes.map((v) => ({ ...v, ...conOpciones(v) }))
              : [
                  {
                    id: producto.id,
                    nombre: producto.nombre,
                    precio: producto.precio_desde,
                    disponible: producto.disponible,
                    ...conOpciones(producto),
                  },
                ]
          }
        />
      </div>

      <IngredienteDialogo ingrediente={ingredienteAbierto} onCerrar={() => setIngredienteAbierto(null)} />
    </div>
  );
}
