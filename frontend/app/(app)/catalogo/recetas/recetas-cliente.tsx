"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { catalogoApi, type Receta, type UnidadMedida } from "@/lib/catalogo";
import { ErrorApi } from "@/lib/proxy";
import { aTitulo } from "@/lib/texto";

/**
 * Todas las recetas, incluidas las que no cuelgan de ningún producto.
 *
 * La ficha del producto sigue siendo el camino normal (ahí se arma la receta
 * de lo que se vende), pero hay dos casos que no caben ahí: las **subrecetas**
 * —masa, salsa, lo que la cocina produce para usar después— y las copias que
 * quedaron sueltas al duplicar. Sin este listado no había forma de verlas.
 */
export function RecetasCliente({
  recetas,
  unidades,
}: {
  recetas: Receta[];
  unidades: UnidadMedida[];
}) {
  const router = useRouter();

  const columnas = useMemo<ColumnDef<Receta>[]>(
    () => [
      {
        accessorKey: "nombre",
        header: "Receta",
        cell: ({ row }) => (
          <Link
            href={`/catalogo/recetas/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {row.original.nombre}
          </Link>
        ),
      },
      {
        id: "rendimiento",
        header: "Rinde",
        accessorFn: (r) =>
          `${Number(r.rendimiento_cantidad)} ${r.rendimiento_unidad_medida_nombre ?? ""}`.trim(),
      },
      {
        id: "produce",
        header: "Produce",
        accessorFn: (r) => (r.articulo_id ? "Subreceta" : "Producto de venta"),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">Recetas</h1>
          <p className="text-xs text-gray">
            Las de venta se arman en la ficha de su producto; acá están todas,
            incluidas las subrecetas de cocina.
          </p>
        </div>
        <DialogoNuevaReceta
          unidades={unidades}
          onCreada={(id) => router.push(`/catalogo/recetas/${id}`)}
        />
      </div>
      <TablaDatos
        columnas={columnas}
        datos={recetas}
        placeholderBusqueda="Buscar receta..."
      />
    </div>
  );
}

function DialogoNuevaReceta({
  unidades,
  onCreada,
}: {
  unidades: UnidadMedida[];
  onCreada: (id: string) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [udmId, setUdmId] = useState(unidades[0]?.id ?? "");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setError("");
    setGuardando(true);
    try {
      const receta = await catalogoApi.crearReceta({
        nombre,
        rendimiento_cantidad: cantidad || "1",
        rendimiento_unidad_medida_id: udmId,
      });
      dialogRef.current?.close();
      onCreada(receta.id);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear la receta.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
        disabled={unidades.length === 0}
      >
        + Nueva receta
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nueva receta</h2>
          <p className="-mt-2 text-xs text-gray">
            Los insumos se agregan al abrirla. Si produce una subreceta, se
            indica ahí mismo.
          </p>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onBlur={() => setNombre((n) => aTitulo(n))}
              maxLength={150}
              placeholder="Masa de Pizza"
            />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Rinde
              <input
                value={cantidad}
                onChange={(e) => setCantidad(e.target.value)}
                className="w-24"
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Unidad
              <select value={udmId} onChange={(e) => setUdmId(e.target.value)}>
                {unidades.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={crear}
              disabled={guardando || !nombre.trim() || !udmId}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
            >
              {guardando ? "Creando..." : "Crear y abrir"}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
