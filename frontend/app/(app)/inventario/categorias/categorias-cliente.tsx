"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearCategoriaAction, editarCategoriaAction } from "../actions";

export type Categoria = {
  id: string;
  nombre: string;
  frecuencia_conteo: string | null;
};

// Las seis de `rules.FRECUENCIAS_CONTEO`. Vacío = fuera del conteo cíclico.
const FRECUENCIAS = [
  "diario",
  "semanal",
  "quincenal",
  "mensual",
  "semestral",
  "anual",
] as const;

function SelectorFrecuencia({ valor }: { valor?: string | null }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      Frecuencia de conteo
      <select name="frecuencia_conteo" defaultValue={valor ?? ""}>
        <option value="">Sin conteo cíclico</option>
        {FRECUENCIAS.map((f) => (
          <option key={f} value={f}>
            {f}
          </option>
        ))}
      </select>
      <span className="text-xs font-normal text-gray">
        Cada cuánto toca contar esta categoría (RN-INV-007). No hay un número universal:
        el queso no se cuenta con la misma frecuencia que las servilletas.
      </span>
    </label>
  );
}

function DialogoNuevaCategoria() {
  return (
    <DialogoFormulario
      titulo="Nueva categoría"
      disparador="+ Nueva categoría"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearCategoriaAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} placeholder="Lácteos" />
      </label>
      <SelectorFrecuencia />
    </DialogoFormulario>
  );
}

function DialogoEditarCategoria({ categoria }: { categoria: Categoria }) {
  return (
    <DialogoFormulario
      titulo="Editar categoría"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarCategoriaAction}
      ayuda="Dejarla en 'sin conteo cíclico' la saca del calendario de conteos; no borra los ya hechos."
    >
      <input type="hidden" name="id" value={categoria.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={categoria.nombre} />
      </label>
      <SelectorFrecuencia valor={categoria.frecuencia_conteo} />
    </DialogoFormulario>
  );
}

export function CategoriasCliente({ categorias }: { categorias: Categoria[] }) {
  const columnas: ColumnDef<Categoria>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Categoría" },
      {
        id: "frecuencia",
        header: "Conteo cíclico",
        accessorFn: (c) => c.frecuencia_conteo ?? "—",
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <DialogoEditarCategoria categoria={row.original} />,
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Categorías</h1>
        <DialogoNuevaCategoria />
      </div>
      <p className="text-sm text-gray">
        Agrupan artículos y —esto es lo que decide trabajo real— fijan cada cuánto se
        cuenta cada grupo en el conteo cíclico (RN-INV-007). Hasta ahora solo se
        administraban por API.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={categorias}
        placeholderBusqueda="Buscar categoría..."
      />
    </div>
  );
}
