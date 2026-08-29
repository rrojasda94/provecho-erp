"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  crearCategoriaUdmAction,
  crearUnidadMedidaAction,
  editarUnidadMedidaAction,
} from "../actions";
import { Combobox } from "@/components/ui/combobox";

export type CategoriaUdm = { id: string; nombre: string; unidad_base_id: string | null };
export type UnidadMedida = {
  id: string;
  categoria_udm_id: string;
  nombre: string;
  ratio: string;
  decimales: number;
};

function CamposUnidad({ unidad }: { unidad?: UnidadMedida }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={50} defaultValue={unidad?.nombre ?? ""} />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Ratio contra la unidad base
          <input
            name="ratio"
            type="number"
            min="0"
            step="any"
            defaultValue={unidad?.ratio ?? "1"}
          />
        </label>
        <label className="flex w-32 flex-col gap-1 text-sm font-semibold">
          Decimales
          <input
            name="decimales"
            type="number"
            min={0}
            max={6}
            defaultValue={unidad?.decimales ?? 3}
          />
        </label>
      </div>
      <p className="-mt-2 text-xs text-gray">
        Los decimales deciden con cuánta precisión se teclea una cantidad en esta unidad
        (RN-GER-010): 3 para kilos, 0 para unidades sueltas. No hay un valor universal
        correcto.
      </p>
    </>
  );
}

function DialogoNuevaUnidad({ magnitudes }: { magnitudes: CategoriaUdm[] }) {
  return (
    <DialogoFormulario
      titulo="Nueva unidad de medida"
      disparador="+ Nueva unidad"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearUnidadMedidaAction}
      envioDeshabilitado={magnitudes.length === 0}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Magnitud
        {magnitudes.length === 0 ? (
          <span className="text-xs font-normal text-secondary">
            No hay magnitudes cargadas — creá una primero (peso, volumen, unidad).
          </span>
        ) : (
          <Combobox
            name="categoria_udm_id"
            etiqueta="Magnitud"
            requerido
            marcador="Elegir..."
            opciones={magnitudes.map((m) => ({ valor: m.id, etiqueta: m.nombre }))}
          />
        )}
      </label>
      <CamposUnidad />
    </DialogoFormulario>
  );
}

/** La magnitud no se edita: cambiarla dejaría el ratio comparándose contra
 * otra unidad base, o sea toda conversión ya hecha con esta unidad mal. */
function DialogoEditarUnidad({
  unidad,
  magnitud,
}: {
  unidad: UnidadMedida;
  magnitud: string;
}) {
  return (
    <DialogoFormulario
      titulo="Editar unidad de medida"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarUnidadMedidaAction}
      ayuda={`Magnitud: ${magnitud} — no se cambia, el ratio se compara contra su unidad base.`}
    >
      <input type="hidden" name="id" value={unidad.id} />
      <CamposUnidad unidad={unidad} />
    </DialogoFormulario>
  );
}

function DialogoNuevaMagnitud() {
  return (
    <DialogoFormulario
      titulo="Nueva magnitud"
      disparador="+ Nueva magnitud"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearCategoriaUdmAction}
      claseDisparador="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark hover:bg-cream"
      ayuda="Agrupa unidades convertibles entre sí: peso (kilo, gramo), volumen (litro, ml), unidad."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={50} placeholder="Peso" />
      </label>
    </DialogoFormulario>
  );
}

export function UnidadesCliente({
  unidades,
  magnitudes,
}: {
  unidades: UnidadMedida[];
  magnitudes: CategoriaUdm[];
}) {
  const nombreMagnitud = useMemo(
    () => new Map(magnitudes.map((m) => [m.id, m.nombre])),
    [magnitudes],
  );

  const columnas: ColumnDef<UnidadMedida>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Unidad" },
      {
        id: "magnitud",
        header: "Magnitud",
        accessorFn: (u) => nombreMagnitud.get(u.categoria_udm_id) ?? "—",
      },
      { accessorKey: "ratio", header: "Ratio" },
      { accessorKey: "decimales", header: "Decimales" },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarUnidad
            unidad={row.original}
            magnitud={nombreMagnitud.get(row.original.categoria_udm_id) ?? "—"}
          />
        ),
      },
    ],
    [nombreMagnitud],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Unidades de medida
        </h1>
        <div className="flex gap-2">
          <DialogoNuevaMagnitud />
          <DialogoNuevaUnidad magnitudes={magnitudes} />
        </div>
      </div>
      <p className="text-sm text-gray">
        Catálogo <strong>global</strong>, no por empresa: la conversión kilo↔gramo es la
        misma para cualquiera. Sin al menos una unidad no se puede crear un artículo, y
        hasta ahora solo se cargaban por API.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={unidades}
        placeholderBusqueda="Buscar unidad..."
      />
    </div>
  );
}
