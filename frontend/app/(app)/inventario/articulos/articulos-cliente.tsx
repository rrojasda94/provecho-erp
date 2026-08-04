"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearArticuloAction, type EstadoArticulo } from "./actions";

export type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  unidad_medida_id: string;
  tipo: string;
  categoria_id: string | null;
  costo_promedio: string;
  archivado: boolean;
  controla_lote: boolean;
};

export type Categoria = { id: string; nombre: string };
export type UnidadMedida = { id: string; nombre: string; decimales: number };

// README del módulo: enum extensible, hoy estos 6 valores.
const TIPOS_ARTICULO = [
  "insumo",
  "subreceta",
  "mercaderia",
  "empaque",
  "repuesto",
  "suministro",
] as const;

const ESTADO_INICIAL: EstadoArticulo = { error: "", ok: false };

function DialogoNuevoArticulo({
  categorias,
  unidadesMedida,
}: {
  categorias: Categoria[];
  unidadesMedida: UnidadMedida[];
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearArticuloAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nuevo artículo
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => formRef.current?.reset()}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg italic uppercase text-dark">Nuevo artículo</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Código interno (máx. 4)
            <input name="id_interno" required maxLength={4} placeholder="H001" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input name="nombre" required maxLength={150} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo
            <select name="tipo" defaultValue="insumo">
              {TIPOS_ARTICULO.map((tipo) => (
                <option key={tipo} value={tipo}>
                  {tipo}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Unidad de medida
            {unidadesMedida.length === 0 ? (
              <span className="text-xs font-normal text-secondary">
                No hay unidades de medida cargadas — no se puede crear un artículo todavía.
              </span>
            ) : (
              <select name="unidad_medida_id" required defaultValue="">
                <option value="" disabled>
                  Elegir...
                </option>
                {unidadesMedida.map((udm) => (
                  <option key={udm.id} value={udm.id}>
                    {udm.nombre}
                  </option>
                ))}
              </select>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Categoría (opcional)
            <select name="categoria_id" defaultValue="">
              <option value="">Sin categoría</option>
              {categorias.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Costo promedio inicial
            <input name="costo_promedio" type="number" min={0} step="0.01" defaultValue="0" />
          </label>
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
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
              type="submit"
              disabled={pendiente || unidadesMedida.length === 0}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
            >
              {pendiente ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function ArticulosCliente({
  articulos,
  categorias,
  unidadesMedida,
}: {
  articulos: Articulo[];
  categorias: Categoria[];
  unidadesMedida: UnidadMedida[];
}) {
  const nombreCategoria = useMemo(
    () => new Map(categorias.map((c) => [c.id, c.nombre])),
    [categorias],
  );
  const nombreUdm = useMemo(
    () => new Map(unidadesMedida.map((u) => [u.id, u.nombre])),
    [unidadesMedida],
  );

  const columnas: ColumnDef<Articulo>[] = useMemo(
    () => [
      { accessorKey: "id_interno", header: "Código" },
      { accessorKey: "nombre", header: "Nombre" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "categoria",
        header: "Categoría",
        accessorFn: (a) => (a.categoria_id ? nombreCategoria.get(a.categoria_id) : "—") ?? "—",
      },
      {
        id: "unidad_medida",
        header: "UdM",
        accessorFn: (a) => nombreUdm.get(a.unidad_medida_id) ?? "—",
      },
      { accessorKey: "costo_promedio", header: "Costo promedio" },
      {
        accessorKey: "archivado",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<boolean>()
                ? "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
                : "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
            }
          >
            {getValue<boolean>() ? "Archivado" : "Activo"}
          </span>
        ),
      },
    ],
    [nombreCategoria, nombreUdm],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Artículos</h1>
        <DialogoNuevoArticulo categorias={categorias} unidadesMedida={unidadesMedida} />
      </div>
      <TablaDatos columnas={columnas} datos={articulos} placeholderBusqueda="Buscar artículo..." />
    </div>
  );
}
