"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { guardarAlmacenAction } from "../actions";

export type Sucursal = { id: string; nombre: string };
export type Almacen = {
  id: string;
  empresa_id: string;
  sucursal_id: string | null;
  nombre: string;
  tipo: string;
  direccion: string | null;
  almacen_abastecedor_id: string | null;
};

function CamposAlmacen({
  sucursales,
  almacenes,
  almacen,
}: {
  sucursales: Sucursal[];
  almacenes: Almacen[];
  almacen?: Almacen;
}) {
  const a: Partial<Almacen> = almacen ?? {};
  // Un almacén no se abastece a sí mismo: el ciclo dejaría el reabastecimiento
  // pidiéndose stock a sí mismo para siempre.
  const abastecedores = almacenes.filter((otro) => otro.id !== a.id);

  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={100} defaultValue={valor(a.nombre)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <input
          name="tipo"
          required
          maxLength={30}
          defaultValue={valor(a.tipo)}
          placeholder="central, cocina, barra, congelados..."
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Sucursal
        <select name="sucursal_id" defaultValue={valor(a.sucursal_id)}>
          <option value="">Sin sucursal (almacén central de la empresa)</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Dirección
        <input name="direccion" maxLength={255} defaultValue={valor(a.direccion)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén abastecedor
        <select
          name="almacen_abastecedor_id"
          defaultValue={valor(a.almacen_abastecedor_id)}
        >
          <option value="">Ninguno (se abastece por compra)</option>
          {abastecedores.map((otro) => (
            <option key={otro.id} value={otro.id}>
              {otro.nombre}
            </option>
          ))}
        </select>
        <span className="text-xs font-normal text-gray">
          A quién le pide stock cuando le falta: el central despacha, el local recibe.
        </span>
      </label>
    </>
  );
}

function DialogoNuevoAlmacen({
  sucursales,
  almacenes,
}: {
  sucursales: Sucursal[];
  almacenes: Almacen[];
}) {
  return (
    <DialogoFormulario
      titulo="Nuevo almacén"
      disparador="+ Nuevo almacén"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={guardarAlmacenAction}
    >
      <CamposAlmacen sucursales={sucursales} almacenes={almacenes} />
    </DialogoFormulario>
  );
}

function DialogoEditarAlmacen({
  almacen,
  sucursales,
  almacenes,
}: {
  almacen: Almacen;
  sucursales: Sucursal[];
  almacenes: Almacen[];
}) {
  return (
    <DialogoFormulario
      titulo="Editar almacén"
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={guardarAlmacenAction}
      ayuda="El stock ya registrado no se mueve: cambiar la sucursal cambia quién administra este almacén, no dónde está la mercadería."
    >
      <input type="hidden" name="id" value={almacen.id} />
      <CamposAlmacen sucursales={sucursales} almacenes={almacenes} almacen={almacen} />
    </DialogoFormulario>
  );
}

export function AlmacenesCliente({
  almacenes,
  sucursales,
}: {
  almacenes: Almacen[];
  sucursales: Sucursal[];
}) {
  const nombreSucursal = useMemo(
    () => new Map(sucursales.map((s) => [s.id, s.nombre])),
    [sucursales],
  );
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );

  const columnas: ColumnDef<Almacen>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Almacén" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        id: "sucursal",
        header: "Sucursal",
        accessorFn: (a) => (a.sucursal_id ? nombreSucursal.get(a.sucursal_id) : "—") ?? "—",
      },
      {
        id: "abastecedor",
        header: "Se abastece de",
        accessorFn: (a) =>
          (a.almacen_abastecedor_id ? nombreAlmacen.get(a.almacen_abastecedor_id) : "—") ??
          "—",
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <DialogoEditarAlmacen
            almacen={row.original}
            sucursales={sucursales}
            almacenes={almacenes}
          />
        ),
      },
    ],
    [nombreSucursal, nombreAlmacen, sucursales, almacenes],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl italic uppercase text-dark">Almacenes</h1>
        <DialogoNuevoAlmacen sucursales={sucursales} almacenes={almacenes} />
      </div>
      <p className="text-sm text-gray">
        Dónde vive el stock. El <strong>abastecedor</strong> es de quién pide cuando le
        falta: el local solicita, el supervisor aprueba y reserva, el central despacha
        por FEFO.
      </p>
      <TablaDatos
        columnas={columnas}
        datos={almacenes}
        placeholderBusqueda="Buscar almacén..."
      />
    </div>
  );
}
