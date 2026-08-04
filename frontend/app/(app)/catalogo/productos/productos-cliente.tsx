"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { catalogoApi, type Marca, type Producto } from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { aTitulo } from "@/lib/texto";

/** Qué se está creando. La diferencia no es cosmética: un producto con
 * variantes nace sin receta (la lleva cada hija) y un extra nace marcado
 * `es_extra` para no salir suelto en la carta. */
type Tipo = "simple" | "con_variantes" | "extra";

export function ProductosCliente({
  productos,
  marcas,
}: {
  productos: Producto[];
  marcas: Marca[];
}) {
  const router = useRouter();
  // Las variantes no se listan sueltas: se ven y se editan dentro de su
  // padre, igual que en el PDV.
  const raices = useMemo(
    () => productos.filter((p) => !p.producto_padre_id),
    [productos],
  );

  const columnas = useMemo<ColumnDef<Producto>[]>(
    () => [
      {
        accessorKey: "nombre",
        header: "Producto",
        cell: ({ row }) => (
          <Link
            href={`/catalogo/productos/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {row.original.nombre}
          </Link>
        ),
      },
      { accessorKey: "id_interno", header: "Código" },
      {
        id: "clase",
        header: "Tipo",
        accessorFn: (p) =>
          p.es_extra ? "Extra" : p.receta_id ? "Simple" : "Con variantes",
      },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<boolean>() ? "Activo" : "Inactivo"}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Productos comerciales
        </h1>
        <DialogoNuevoProducto
          marcas={marcas}
          onCreado={(id) => router.push(`/catalogo/productos/${id}`)}
        />
      </div>
      <TablaDatos
        columnas={columnas}
        datos={raices}
        placeholderBusqueda="Buscar producto..."
      />
    </div>
  );
}

function DialogoNuevoProducto({
  marcas,
  onCreado,
}: {
  marcas: Marca[];
  onCreado: (id: string) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [idInterno, setIdInterno] = useState("");
  const [marcaId, setMarcaId] = useState(marcas[0]?.id ?? "");
  const [tipo, setTipo] = useState<Tipo>("con_variantes");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setError("");
    setGuardando(true);
    try {
      const producto = await catalogoApi.crearProducto({
        id_interno: idInterno.trim().toUpperCase(),
        marca_id: marcaId,
        nombre,
        es_extra: tipo === "extra",
      });
      dialogRef.current?.close();
      onCreado(producto.id);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear el producto.");
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
        disabled={marcas.length === 0}
      >
        + Nuevo producto
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nuevo producto</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              // Formato título al salir del campo: el mismo insumo escrito
              // de tres formas son tres filas distintas en un reporte.
              onBlur={() => setNombre((n) => aTitulo(n))}
              maxLength={150}
              placeholder="Pizza de Peperoni"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código interno (4)
            <input
              value={idInterno}
              onChange={(e) => setIdInterno(e.target.value.slice(0, 4))}
              maxLength={4}
              placeholder="PZPE"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Marca
            <select value={marcaId} onChange={(e) => setMarcaId(e.target.value)}>
              {marcas.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="flex flex-col gap-2 text-sm">
            <legend className="font-semibold">¿Cómo se vende?</legend>
            {(
              [
                ["con_variantes", "Con variantes (Personal, Mediana, Familiar)"],
                ["simple", "Producto simple: una sola receta y un solo precio"],
                ["extra", "Extra: se agrega a otro producto, no se vende solo"],
              ] as const
            ).map(([valor, etiqueta]) => (
              <label key={valor} className="flex items-center gap-2 font-normal">
                <input
                  type="radio"
                  name="tipo"
                  checked={tipo === valor}
                  onChange={() => setTipo(valor)}
                />
                {etiqueta}
              </label>
            ))}
          </fieldset>
          <p className="-mt-2 text-xs text-gray">
            La receta se arma en la ficha, después de crearlo. Un producto con
            variantes no lleva receta propia: la lleva cada variante.
          </p>
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
              disabled={guardando || !nombre.trim() || idInterno.length === 0}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
            >
              {guardando ? "Creando..." : "Crear y abrir ficha"}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
