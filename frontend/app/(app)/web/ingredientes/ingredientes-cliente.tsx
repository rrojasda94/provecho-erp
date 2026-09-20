"use client";

import { useActionState, useTransition } from "react";

import { ESTADO_INICIAL } from "@/lib/errores";

import {
  borrarFotoAction,
  guardarDescripcionArticuloAction,
  subirFotoAction,
} from "../actions";

export type Insumo = {
  id: string;
  nombre: string;
  nombre_publico: string | null;
  descripcion: string | null;
  archivado: boolean;
};

export type Foto = {
  id: string;
  nombre: string;
  url_storage: string;
  created_at: string;
};

function FormDescripcion({ insumo }: { insumo: Insumo }) {
  const [estado, formAction, pendiente] = useActionState(
    guardarDescripcionArticuloAction,
    ESTADO_INICIAL,
  );
  return (
    <form action={formAction} className="flex flex-1 flex-col gap-1">
      <input type="hidden" name="articulo_id" value={insumo.id} />
      {/* El nombre del artículo está escrito para el almacén ("QUESO EDAM
          BLOQUE 3KG") y el sitio lo mostraba tal cual bajo cada pizza.
          Renombrarlo no es opción: el almacén necesita distinguir dos quesos
          que al cliente le dan igual. */}
      <label className="flex flex-col gap-1 text-xs font-semibold text-gray">
        Nombre para el cliente
        <input
          name="nombre_publico"
          maxLength={80}
          placeholder={`Vacío = se muestra "${insumo.nombre}"`}
          defaultValue={insumo.nombre_publico ?? ""}
          className="text-sm font-normal text-dark"
        />
      </label>
      <textarea
        name="descripcion"
        rows={2}
        maxLength={500}
        placeholder="Qué es y de dónde sale — se muestra al hacer clic en el ingrediente"
        defaultValue={insumo.descripcion ?? ""}
        className="text-sm"
      />
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={pendiente}
          className="self-start rounded bg-primary px-3 py-1 text-xs font-bold text-white hover:bg-primary/90 disabled:opacity-60"
        >
          {pendiente ? "Guardando..." : "Guardar"}
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

function Fotos({ insumoId, fotos }: { insumoId: string; fotos: Foto[] }) {
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
        <input type="hidden" name="entidad" value="ingrediente" />
        <input type="hidden" name="entidad_id" value={insumoId} />
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

export function IngredientesCliente({
  insumos,
  fotosPorInsumo,
}: {
  insumos: Insumo[];
  fotosPorInsumo: Record<string, Foto[]>;
}) {
  const activos = insumos.filter((i) => !i.archivado);
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Ingredientes del sitio web
        </h1>
        <p className="text-sm text-gray">
          Nombre, descripción y foto que ve el cliente cuando toca un
          ingrediente dentro de una pizza. El nombre del almacén no cambia.
        </p>
      </div>
      <div className="flex flex-col gap-3">
        {activos.map((i) => (
          <div
            key={i.id}
            className="flex flex-col gap-2 rounded-lg border border-border bg-white p-4 sm:flex-row sm:items-start"
          >
            <div className="w-full sm:w-40 sm:shrink-0">
              <h3 className="font-semibold text-dark">{i.nombre}</h3>
              {i.nombre_publico && (
                <p className="text-xs text-gray">En la web: {i.nombre_publico}</p>
              )}
              <Fotos insumoId={i.id} fotos={fotosPorInsumo[i.id] ?? []} />
            </div>
            <FormDescripcion insumo={i} />
          </div>
        ))}
        {activos.length === 0 && (
          <p className="text-sm text-gray">No hay insumos cargados todavía.</p>
        )}
      </div>
    </div>
  );
}
