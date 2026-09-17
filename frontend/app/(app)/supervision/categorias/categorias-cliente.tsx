"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { InsigniaActiva } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { alternarActivaAction, crearCategoriaAction } from "./actions";

export type Categoria = { id: string; nombre: string; activa: boolean };

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
        <input name="nombre" required maxLength={80} />
      </label>
    </DialogoFormulario>
  );
}

/** Categorías libres por empresa (limpieza, apertura, mantenimiento...):
 * sin catálogo cerrado en código, las crea el supervisor. */
export function CategoriasCliente({ categorias }: { categorias: Categoria[] }) {
  const router = useRouter();
  const [pendiente, iniciarTransicion] = useTransition();

  const columnas: ColumnDef<Categoria>[] = [
    { accessorKey: "nombre", header: "Nombre" },
    {
      id: "activa",
      header: "Estado",
      cell: ({ row }) => (
        <button
          type="button"
          disabled={pendiente}
          onClick={() =>
            iniciarTransicion(async () => {
              await alternarActivaAction(row.original.id, !row.original.activa);
              router.refresh();
            })
          }
        >
          <InsigniaActiva activa={row.original.activa} />
        </button>
      ),
    },
  ];

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Categorías de tarea</h1>
        <DialogoNuevaCategoria />
      </div>
      <TablaDatos columnas={columnas} datos={categorias} placeholderBusqueda="Buscar..." />
    </div>
  );
}
