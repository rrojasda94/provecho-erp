"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import { buscar, type Buscable } from "@/lib/busqueda";

export type Ingrediente = { id: string; nombre: string };
export type Variante = {
  id: string;
  nombre: string;
  precio: string;
  disponible: boolean;
  ingredientes: Ingrediente[];
};
export type Producto = {
  id: string;
  nombre: string;
  descripcion: string | null;
  categoria_id: string | null;
  precio_desde: string;
  foto_url: string | null;
  disponible: boolean;
  ingredientes: Ingrediente[];
  variantes: Variante[];
};
export type Categoria = { id: string; nombre: string };
export type Carta = { categorias: Categoria[]; productos: Producto[] };

function terminosDe(p: Producto): string[] {
  return [
    p.nombre,
    ...p.variantes.map((v) => v.nombre),
    ...p.ingredientes.map((i) => i.nombre),
    ...p.variantes.flatMap((v) => v.ingredientes.map((i) => i.nombre)),
  ];
}

export function CartaCliente({ carta }: { carta: Carta }) {
  const [consulta, setConsulta] = useState("");
  const [categoria, setCategoria] = useState<string | null>(null);
  const [tamano, setTamano] = useState<string>("");
  const [precioMax, setPrecioMax] = useState<string>("");
  const [soloDisponibles, setSoloDisponibles] = useState(false);

  const tamanos = useMemo(() => {
    const set = new Set<string>();
    for (const p of carta.productos) for (const v of p.variantes) set.add(v.nombre);
    return [...set].sort();
  }, [carta.productos]);

  const buscables: Buscable[] = useMemo(
    () => carta.productos.map((p) => ({ id: p.id, terminos: terminosDe(p) })),
    [carta.productos],
  );

  const idsPorBusqueda = useMemo(() => new Set(buscar(consulta, buscables)), [consulta, buscables]);

  const filtrados = useMemo(() => {
    return carta.productos.filter((p) => {
      if (!idsPorBusqueda.has(p.id)) return false;
      if (categoria && p.categoria_id !== categoria) return false;
      if (tamano && !(p.variantes.length === 0 || p.variantes.some((v) => v.nombre === tamano))) {
        return false;
      }
      if (precioMax && Number(p.precio_desde) > Number(precioMax)) return false;
      if (soloDisponibles && !p.disponible) return false;
      return true;
    });
  }, [carta.productos, idsPorBusqueda, categoria, tamano, precioMax, soloDisponibles]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <h1 className="font-display text-3xl uppercase text-negro">Carta</h1>

      <div className="flex flex-col gap-3">
        <input
          type="search"
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
          placeholder="Busca por nombre o ingrediente (ej. champiñón, peperoni)"
          className="w-full rounded border-2 border-negro bg-white px-4 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setCategoria(null)}
            className={`rounded-full border-2 border-negro px-3 py-1 text-xs font-bold uppercase ${
              categoria === null ? "bg-verde text-negro" : "bg-white"
            }`}
          >
            Todas
          </button>
          {carta.categorias.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setCategoria(c.id)}
              className={`rounded-full border-2 border-negro px-3 py-1 text-xs font-bold uppercase ${
                categoria === c.id ? "bg-verde text-negro" : "bg-white"
              }`}
            >
              {c.nombre}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {tamanos.length > 0 && (
            <label className="flex items-center gap-1">
              Tamaño
              <select
                value={tamano}
                onChange={(e) => setTamano(e.target.value)}
                className="rounded border border-negro/40 px-2 py-1"
              >
                <option value="">Todos</option>
                {tamanos.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="flex items-center gap-1">
            Precio hasta
            <input
              type="number"
              min={0}
              value={precioMax}
              onChange={(e) => setPrecioMax(e.target.value)}
              placeholder="S/"
              className="w-20 rounded border border-negro/40 px-2 py-1"
            />
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={soloDisponibles}
              onChange={(e) => setSoloDisponibles(e.target.checked)}
            />
            Solo disponibles
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtrados.map((p) => (
          <Link
            key={p.id}
            href={`/carta/${p.id}`}
            className="sombra-dura flex flex-col overflow-hidden rounded-lg border-2 border-negro bg-white"
          >
            <div className="relative h-40 w-full bg-crema-2">
              {p.foto_url && <Image src={p.foto_url} alt={p.nombre} fill className="object-cover" />}
              {!p.disponible && (
                <span className="absolute left-2 top-2 rounded bg-rojo px-2 py-0.5 text-xs font-bold text-white">
                  No disponible
                </span>
              )}
            </div>
            <div className="flex flex-1 flex-col gap-1 p-3">
              <h3 className="font-bold">{p.nombre}</h3>
              {p.descripcion && (
                <p className="line-clamp-2 flex-1 text-xs text-humo">{p.descripcion}</p>
              )}
              <p className="font-display text-lg text-verde">Desde S/ {p.precio_desde}</p>
            </div>
          </Link>
        ))}
        {filtrados.length === 0 && (
          <p className="col-span-full text-center text-sm text-humo">
            No encontramos nada con esos filtros.
          </p>
        )}
      </div>
    </div>
  );
}
