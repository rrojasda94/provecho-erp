"use client";

import { useActionState, useTransition } from "react";

import { ESTADO_INICIAL } from "@/lib/errores";

import {
  borrarFotoAction,
  guardarDescripcionProductoAction,
  subirFotoAction,
} from "../actions";

export type Producto = {
  id: string;
  nombre: string;
  descripcion: string | null;
  activo: boolean;
  es_extra: boolean;
  producto_padre_id: string | null;
};

export type Foto = {
  id: string;
  nombre: string;
  url_storage: string;
  created_at: string;
};

function FormDescripcion({ producto }: { producto: Producto }) {
  const [estado, formAction, pendiente] = useActionState(
    guardarDescripcionProductoAction,
    ESTADO_INICIAL,
  );
  return (
    <form action={formAction} className="flex flex-1 flex-col gap-1">
      <input type="hidden" name="producto_id" value={producto.id} />
      <textarea
        name="descripcion"
        rows={2}
        maxLength={500}
        placeholder="Qué lleva y por qué pedirla — se muestra en el sitio público"
        defaultValue={producto.descripcion ?? ""}
        className="text-sm"
      />
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={pendiente}
          className="self-start rounded bg-primary px-3 py-1 text-xs font-bold text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {pendiente ? "Guardando..." : "Guardar descripción"}
        </button>
        {estado.error && <span className="text-xs text-secondary">{estado.error}</span>}
        {estado.ok && <span className="text-xs text-accent">Guardado.</span>}
      </div>
    </form>
  );
}

function BotonBorrarFoto({ archivoId }: { archivoId: string }) {
  const [pendiente, startTransition] = useTransition();
  return (
    <button
      type="button"
      disabled={pendiente}
      onClick={() => startTransition(() => void borrarFotoAction(archivoId))}
      className="absolute right-1 top-1 rounded-full bg-dark/70 px-1.5 text-xs text-white hover:bg-secondary"
      aria-label="Quitar foto"
    >
      ×
    </button>
  );
}

function Fotos({ productoId, fotos }: { productoId: string; fotos: Foto[] }) {
  const [estado, formAction, pendiente] = useActionState(subirFotoAction, ESTADO_INICIAL);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {fotos.map((f) => (
          <div key={f.id} className="relative h-16 w-16 overflow-hidden rounded border border-border">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={f.url_storage} alt={f.nombre} className="h-full w-full object-cover" />
            <BotonBorrarFoto archivoId={f.id} />
          </div>
        ))}
        {fotos.length === 0 && (
          <span className="text-xs text-gray">Sin fotos — el sitio muestra un placeholder.</span>
        )}
      </div>
      <form action={formAction} className="flex items-center gap-2">
        <input type="hidden" name="entidad" value="producto" />
        <input type="hidden" name="entidad_id" value={productoId} />
        <input type="file" name="archivo" accept="image/jpeg,image/png,image/webp" required />
        <button
          type="submit"
          disabled={pendiente}
          className="rounded border border-border px-3 py-1 text-xs font-bold hover:bg-cream disabled:opacity-60"
        >
          {pendiente ? "Subiendo..." : "Subir foto"}
        </button>
      </form>
      {estado.error && <span className="text-xs text-secondary">{estado.error}</span>}
    </div>
  );
}

export function CartaCliente({
  productos,
  fotosPorProducto,
}: {
  productos: Producto[];
  fotosPorProducto: Record<string, Foto[]>;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">Carta del sitio web</h1>
        <p className="text-sm text-gray">
          Descripción y fotos que ve el cliente en el sitio público. Los
          ingredientes salen solos de la receta de cada producto — se
          describen en{" "}
          <a href="/web/ingredientes" className="underline">
            Ingredientes
          </a>
          .
        </p>
      </div>
      <div className="flex flex-col gap-3">
        {productos.map((p) => (
          <div
            key={p.id}
            className="flex flex-col gap-2 rounded-lg border border-border bg-white p-4 sm:flex-row sm:items-start"
          >
            <div className="w-full sm:w-40 sm:shrink-0">
              <h3 className="font-semibold text-dark">{p.nombre}</h3>
              <Fotos productoId={p.id} fotos={fotosPorProducto[p.id] ?? []} />
            </div>
            <FormDescripcion producto={p} />
          </div>
        ))}
        {productos.length === 0 && (
          <p className="text-sm text-gray">Esta marca todavía no tiene productos activos.</p>
        )}
      </div>
    </div>
  );
}
