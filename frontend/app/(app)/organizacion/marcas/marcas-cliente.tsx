"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { guardarMarcaAction } from "../actions";

export type Marca = { id: string; grupo_id: string; nombre: string; tipo: string };

function CamposMarca({ marca }: { marca?: Marca }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input
          name="nombre"
          required
          maxLength={100}
          defaultValue={marca?.nombre ?? ""}
          placeholder="Charlie's Pizzas"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <input
          name="tipo"
          required
          maxLength={50}
          defaultValue={marca?.tipo ?? ""}
          placeholder="pizzeria, cafeteria, delivery..."
        />
        <span className="text-xs font-normal text-gray">
          Enum extensible por diseño: se escribe, no se elige de una lista cerrada.
        </span>
      </label>
    </>
  );
}

function DialogoNuevaMarca() {
  return (
    <DialogoFormulario
      titulo="Nueva marca"
      disparador="+ Nueva marca"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarMarcaAction}
    >
      <CamposMarca />
    </DialogoFormulario>
  );
}

function DialogoEditarMarca({ marca }: { marca: Marca }) {
  return (
    <DialogoFormulario
      titulo="Editar marca"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarMarcaAction}
    >
      <input type="hidden" name="id" value={marca.id} />
      <CamposMarca marca={marca} />
    </DialogoFormulario>
  );
}

export function MarcasCliente({ marcas }: { marcas: Marca[] }) {
  const columnas: ColumnDef<Marca>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Marca" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <DialogoEditarMarca marca={row.original} />,
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Marcas</h1>
        <DialogoNuevaMarca />
      </div>
      <p className="text-sm text-gray">
        La marca es del <strong>grupo</strong>, y una empresa la opera bajo licencia
        (franquicia interna). Sin esa licencia, una sucursal de esa marca no puede
        existir. Las licencias se otorgan por API.
      </p>
      <TablaDatos columnas={columnas} datos={marcas} placeholderBusqueda="Buscar marca..." />
    </div>
  );
}
