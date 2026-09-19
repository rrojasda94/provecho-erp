"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import { buscar, type Buscable } from "@/lib/busqueda";
import { agregarFavoritoAction, quitarFavoritoAction } from "@/app/cuenta/actions";

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

function BotonFavorito({
  productoId,
  esFavorito,
  sesionActiva,
  onCambio,
}: {
  productoId: string;
  esFavorito: boolean;
  sesionActiva: boolean;
  onCambio: (id: string, favorito: boolean) => void;
}) {
  const [pendiente, startTransition] = useTransition();
  const router = useRouter();

  if (!sesionActiva) {
    return (
      // `<button>` y no `<Link>`: esta tarjeta ya es un `<Link>` de la
      // carta, y un `<a>` anidado dentro de otro `<a>` es HTML inválido —
      // React lo detecta en hidratación y regenera el árbol entero, que es
      // el tipo de parpadeo que un e2e agarra como carrera y un ojo humano
      // casi nunca nota.
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          router.push("/cuenta/ingresar");
        }}
        className="absolute right-2 top-2 rounded-full bg-white/90 px-2 py-1 text-xs"
        title="Ingresa para guardar favoritos"
      >
        ♡
      </button>
    );
  }

  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const nuevoValor = !esFavorito;
        onCambio(productoId, nuevoValor);
        startTransition(async () => {
          try {
            if (nuevoValor) await agregarFavoritoAction(productoId);
            else await quitarFavoritoAction(productoId);
          } catch {
            onCambio(productoId, esFavorito);
          }
        });
      }}
      className="absolute right-2 top-2 rounded-full bg-white/90 px-2 py-1 text-sm"
      title={esFavorito ? "Quitar de favoritos" : "Agregar a favoritos"}
    >
      {esFavorito ? "♥" : "♡"}
    </button>
  );
}

export function CartaCliente({
  carta,
  sesionActiva = false,
  favoritosIds = [],
}: {
  carta: Carta;
  sesionActiva?: boolean;
  favoritosIds?: string[];
}) {
  // Los filtros viven en la URL (`?q=&cat=&tam=`): el "atrás" del celular
  // al volver de un producto no los pierde, y una búsqueda se puede compartir.
  const params = useSearchParams();
  const [consulta, setConsulta] = useState(params.get("q") ?? "");
  const [categoria, setCategoria] = useState<string | null>(params.get("cat"));
  const [tamano, setTamano] = useState(params.get("tam") ?? "");
  const [favoritos, setFavoritos] = useState(() => new Set(favoritosIds));

  useEffect(() => {
    const url = new URLSearchParams();
    if (consulta) url.set("q", consulta);
    if (categoria) url.set("cat", categoria);
    if (tamano) url.set("tam", tamano);
    const texto = url.toString();
    window.history.replaceState(null, "", texto ? `?${texto}` : window.location.pathname);
  }, [consulta, categoria, tamano]);

  function alCambiarFavorito(id: string, favorito: boolean) {
    setFavoritos((actual) => {
      const siguiente = new Set(actual);
      if (favorito) siguiente.add(id);
      else siguiente.delete(id);
      return siguiente;
    });
  }

  const enCategoria = useMemo(
    () => carta.productos.filter((p) => !categoria || p.categoria_id === categoria),
    [carta.productos, categoria],
  );

  // Los tamaños que ofrece lo que hay en la categoría elegida, en el orden de
  // la carta (Personal, Mediana, Familiar): sin categoría con variantes, no
  // hay filtro de tamaño que mostrar.
  const tamanos = useMemo(() => {
    const set = new Set<string>();
    for (const p of enCategoria) for (const v of p.variantes) set.add(v.nombre);
    return [...set];
  }, [enCategoria]);
  const tamanoActivo = tamanos.includes(tamano) ? tamano : "";

  const buscables: Buscable[] = useMemo(
    () => carta.productos.map((p) => ({ id: p.id, terminos: terminosDe(p) })),
    [carta.productos],
  );

  const idsPorBusqueda = useMemo(() => new Set(buscar(consulta, buscables)), [consulta, buscables]);

  const filtrados = useMemo(() => {
    return enCategoria
      .filter((p) => {
        if (!idsPorBusqueda.has(p.id)) return false;
        return !tamanoActivo || p.variantes.some((v) => v.nombre === tamanoActivo);
      })
      // Lo agotado se ve (con su etiqueta) pero al final: no estorba al pedir.
      .sort((a, b) => Number(b.disponible) - Number(a.disponible));
  }, [enCategoria, idsPorBusqueda, tamanoActivo]);

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
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tamaño">
              <span className="font-bold">Tamaño</span>
              {["", ...tamanos].map((t) => (
                <button
                  key={t || "todos"}
                  type="button"
                  onClick={() => setTamano(t)}
                  className={`rounded-full border-2 border-negro px-3 py-1 text-xs font-bold uppercase ${
                    tamanoActivo === t ? "bg-verde text-negro" : "bg-white"
                  }`}
                >
                  {t || "Todos"}
                </button>
              ))}
            </div>
          )}
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
              <BotonFavorito
                productoId={p.id}
                esFavorito={favoritos.has(p.id)}
                sesionActiva={sesionActiva}
                onCambio={alCambiarFavorito}
              />
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
