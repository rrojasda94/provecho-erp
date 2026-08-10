"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { guardarSucursalAction } from "../actions";

export type Marca = { id: string; nombre: string };
export type Sucursal = {
  id: string;
  empresa_id: string;
  marca_id: string;
  nombre: string;
  direccion: string;
  tenencia: string;
  estado: string;
};

const TENENCIAS = ["propia", "alquilada", "del_grupo"] as const;

function CamposSucursal({
  marcas,
  sucursal,
}: {
  marcas: Marca[];
  sucursal?: Sucursal;
}) {
  const s: Partial<Sucursal> = sucursal ?? {};
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Marca
        <select name="marca_id" required defaultValue={valor(s.marca_id)}>
          <option value="" disabled>
            Elegir...
          </option>
          {marcas.map((m) => (
            <option key={m.id} value={m.id}>
              {m.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={valor(s.nombre)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Dirección
        <input name="direccion" required maxLength={255} defaultValue={valor(s.direccion)} />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Tenencia
          <select name="tenencia" defaultValue={s.tenencia ?? "alquilada"}>
            {TENENCIAS.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Estado
          <select name="estado" defaultValue={s.estado ?? "activa"}>
            <option value="activa">Activa</option>
            <option value="inactiva">Inactiva (local cerrado)</option>
          </select>
        </label>
      </div>
    </>
  );
}

function DialogoNuevaSucursal({ marcas }: { marcas: Marca[] }) {
  return (
    <DialogoFormulario
      titulo="Nueva sucursal"
      disparador="+ Nueva sucursal"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarSucursalAction}
      envioDeshabilitado={marcas.length === 0}
      ayuda={
        marcas.length === 0
          ? "No hay marcas cargadas: una sucursal siempre opera bajo una."
          : undefined
      }
    >
      <CamposSucursal marcas={marcas} />
    </DialogoFormulario>
  );
}

/** Cerrar un local es `estado="inactiva"`: no hay baja de sucursal porque
 * sigue siendo el ancla de sus ventas, cajas y trabajadores. */
function DialogoEditarSucursal({
  sucursal,
  marcas,
}: {
  sucursal: Sucursal;
  marcas: Marca[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar sucursal"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarSucursalAction}
      ayuda="Cerrar un local es dejarlo 'inactiva': no se da de baja, sigue siendo el ancla de sus ventas, cajas y trabajadores."
    >
      <input type="hidden" name="id" value={sucursal.id} />
      <CamposSucursal marcas={marcas} sucursal={sucursal} />
    </DialogoFormulario>
  );
}

export function SucursalesCliente({
  sucursales,
  marcas,
}: {
  sucursales: Sucursal[];
  marcas: Marca[];
}) {
  const nombreMarca = useMemo(
    () => new Map(marcas.map((m) => [m.id, m.nombre])),
    [marcas],
  );

  const columnas: ColumnDef<Sucursal>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Sucursal" },
      {
        id: "marca",
        header: "Marca",
        accessorFn: (s) => nombreMarca.get(s.marca_id) ?? "—",
      },
      { accessorKey: "direccion", header: "Dirección" },
      {
        accessorKey: "tenencia",
        header: "Tenencia",
        cell: ({ getValue }) => getValue<string>().replace("_", " "),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => (
          <span
            className={
              getValue<string>() === "activa"
                ? "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
                : "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
            }
          >
            {getValue<string>()}
          </span>
        ),
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <DialogoEditarSucursal sucursal={row.original} marcas={marcas} />,
      },
    ],
    [nombreMarca, marcas],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Sucursales</h1>
        <DialogoNuevaSucursal marcas={marcas} />
      </div>
      <p className="text-sm text-gray">
        Cada local, con la marca bajo la que opera. Es la unidad sobre la que se abre caja,
        se vende y se asigna personal, así que no se elimina: un local cerrado queda{" "}
        <strong>inactiva</strong>.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={sucursales}
        placeholderBusqueda="Buscar sucursal..."
      />
    </div>
  );
}
