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
import { CampoDireccion } from "@/components/direccion/campo-direccion";

export type Marca = { id: string; nombre: string };
export type Almacen = {
  id: string;
  sucursal_id: string | null;
  nombre: string;
  almacen_abastecedor_id: string | null;
  almacen_abastecedor_respaldo_id: string | null;
};
export type Sucursal = {
  id: string;
  empresa_id: string;
  marca_id: string;
  nombre: string;
  direccion: string;
  tenencia: string;
  estado: string;
  ubicacion_place_id: string | null;
  ubicacion_lat: string | number | null;
  ubicacion_lng: string | number | null;
  ubicacion_plus_code: string | null;
  ubicacion_distrito: string | null;
};

const TENENCIAS = ["propia", "alquilada", "del_grupo"] as const;

/**
 * De quién se abastece el local.
 *
 * El dato vive en `almacen` y no en `sucursal` —el que se abastece es el
 * almacén, y una sucursal puede tener más de uno— pero se edita acá porque es
 * acá donde uno lo busca. Con más de un almacén la pregunta deja de tener una
 * sola respuesta, así que se manda a Almacenes en vez de elegir por el
 * usuario cuál de los dos configura.
 */
function Abastecimiento({
  propios,
  almacenes,
}: {
  propios: Almacen[];
  almacenes: Almacen[];
}) {
  if (propios.length === 0) {
    return (
      <p className="text-xs text-gray">
        Esta sucursal todavía no tiene almacén. Créalo en Organización →
        Almacenes y ahí se elige de quién se abastece.
      </p>
    );
  }
  if (propios.length > 1) {
    return (
      <p className="text-xs text-gray">
        Esta sucursal tiene {propios.length} almacenes y cada uno se abastece
        por su cuenta: se configuran en Organización → Almacenes.
      </p>
    );
  }
  const propio = propios[0];
  const otros = almacenes.filter((a) => a.id !== propio.id);
  return (
    <>
      <input type="hidden" name="almacen_id" value={propio.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Se abastece de
        <select
          name="almacen_abastecedor_id"
          defaultValue={valor(propio.almacen_abastecedor_id)}
        >
          <option value="">Ninguno (se abastece por compra)</option>
          {otros.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Y si ese no está, de
        <select
          name="almacen_abastecedor_respaldo_id"
          defaultValue={valor(propio.almacen_abastecedor_respaldo_id)}
        >
          <option value="">Ninguno</option>
          {otros.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
        <span className="text-xs font-normal text-gray">
          Puede ser el almacén de otra sucursal. Se usa cuando el principal
          está dado de baja; distinto del principal.
        </span>
      </label>
    </>
  );
}

function CamposSucursal({
  marcas,
  almacenes,
  sucursal,
}: {
  marcas: Marca[];
  almacenes: Almacen[];
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
      <CampoDireccion
        requerido
        defaultValue={s.direccion}
        ubicacion={sucursal ?? null}
      />
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
      {/* Solo al editar: en el alta la sucursal todavía no tiene almacén al
          que colgarle la configuración. */}
      {sucursal && (
        <Abastecimiento
          propios={almacenes.filter((a) => a.sucursal_id === sucursal.id)}
          almacenes={almacenes}
        />
      )}
    </>
  );
}

function DialogoNuevaSucursal({
  marcas,
  almacenes,
}: {
  marcas: Marca[];
  almacenes: Almacen[];
}) {
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
      <CamposSucursal marcas={marcas} almacenes={almacenes} />
    </DialogoFormulario>
  );
}

/** Cerrar un local es `estado="inactiva"`: no hay baja de sucursal porque
 * sigue siendo el ancla de sus ventas, cajas y trabajadores. */
function DialogoEditarSucursal({
  sucursal,
  marcas,
  almacenes,
}: {
  sucursal: Sucursal;
  marcas: Marca[];
  almacenes: Almacen[];
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
      <CamposSucursal marcas={marcas} almacenes={almacenes} sucursal={sucursal} />
    </DialogoFormulario>
  );
}

export function SucursalesCliente({
  sucursales,
  marcas,
  almacenes,
}: {
  sucursales: Sucursal[];
  marcas: Marca[];
  almacenes: Almacen[];
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
        cell: ({ row }) => (
          <DialogoEditarSucursal
            sucursal={row.original}
            marcas={marcas}
            almacenes={almacenes}
          />
        ),
      },
    ],
    [nombreMarca, marcas, almacenes],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Sucursales</h1>
        <DialogoNuevaSucursal marcas={marcas} almacenes={almacenes} />
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
