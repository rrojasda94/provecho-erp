"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, useTransition } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import {
  darDeBajaAlmacenAction,
  guardarAlmacenAction,
  reactivarAlmacenAction,
} from "../actions";
import { CampoDireccion } from "@/components/direccion/campo-direccion";

export type Sucursal = { id: string; nombre: string };
export type Almacen = {
  id: string;
  empresa_id: string;
  sucursal_id: string | null;
  nombre: string;
  tipo: string;
  direccion: string | null;
  ubicacion_place_id: string | null;
  ubicacion_lat: string | number | null;
  ubicacion_lng: string | number | null;
  ubicacion_plus_code: string | null;
  ubicacion_distrito: string | null;
  almacen_abastecedor_id: string | null;
  almacen_abastecedor_respaldo_id: string | null;
  // Solo llega en `true` cuando la pantalla pidió `incluir_baja`, que exige
  // `organizacion.gestionar`. El resto del ERP no recibe estos almacenes.
  de_baja?: boolean;
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
        <Combobox
          name="sucursal_id"
          etiqueta="Sucursal"
          defaultValue={a.sucursal_id}
          marcador="Sin sucursal (almacén central de la empresa)"
          opciones={sucursales.map((s) => ({ valor: s.id, etiqueta: s.nombre }))}
        />
      </label>
      <CampoDireccion defaultValue={a.direccion} ubicacion={almacen ?? null} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén abastecedor
        <Combobox
          name="almacen_abastecedor_id"
          etiqueta="Almacén abastecedor"
          defaultValue={a.almacen_abastecedor_id}
          marcador="Ninguno (se abastece por compra)"
          opciones={abastecedores.map((otro) => ({ valor: otro.id, etiqueta: otro.nombre }))}
        />
        <span className="text-xs font-normal text-gray">
          A quién le pide stock cuando le falta: el central despacha, el local recibe.
        </span>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Abastecedor de respaldo
        <Combobox
          name="almacen_abastecedor_respaldo_id"
          etiqueta="Almacén de respaldo"
          defaultValue={a.almacen_abastecedor_respaldo_id}
          marcador="Ninguno"
          opciones={abastecedores.map((otro) => ({ valor: otro.id, etiqueta: otro.nombre }))}
        />
        <span className="text-xs font-normal text-gray">
          A quién se le pide si el principal está dado de baja. Puede ser el
          almacén de otra sucursal.
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

/**
 * Baja y reactivación en el mismo botón: son el mismo estado visto desde sus
 * dos lados, y separarlos dejaba una acción visible que nunca aplica a la
 * fila que se está mirando.
 *
 * La baja pregunta; reactivar no —deshacer algo no necesita confirmación—.
 */
function BotonBaja({
  almacen,
  onError,
}: {
  almacen: Almacen;
  onError: (mensaje: string) => void;
}) {
  const [pendiente, startTransition] = useTransition();
  const deBaja = almacen.de_baja === true;

  const correr = () => {
    if (
      !deBaja &&
      !window.confirm(
        `¿Dar de baja el almacén «${almacen.nombre}»? Deja de aparecer en compras, ` +
          `inventario y producción. Se puede reactivar después.`,
      )
    ) {
      return;
    }
    onError("");
    startTransition(async () => {
      const r = deBaja
        ? await reactivarAlmacenAction(almacen.id)
        : await darDeBajaAlmacenAction(almacen.id);
      if (!r.ok) onError(r.error);
    });
  };

  return (
    <button type="button" className={BOTON_FILA} onClick={correr} disabled={pendiente}>
      {deBaja ? "Reactivar" : "Dar de baja"}
    </button>
  );
}

export function AlmacenesCliente({
  almacenes,
  sucursales,
  puedeGestionar,
}: {
  almacenes: Almacen[];
  sucursales: Sucursal[];
  puedeGestionar: boolean;
}) {
  const [error, setError] = useState("");
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
      {
        accessorKey: "nombre",
        header: "Almacén",
        // Un almacén de baja sigue en la tabla —es la única pantalla donde se
        // puede recuperar— pero tiene que leerse distinto de uno vivo.
        cell: ({ row }) =>
          row.original.de_baja ? (
            <span className="text-gray line-through">{row.original.nombre}</span>
          ) : (
            row.original.nombre
          ),
      },
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
          <div className="flex justify-end gap-1">
            {!row.original.de_baja && (
              <DialogoEditarAlmacen
                almacen={row.original}
                sucursales={sucursales}
                almacenes={almacenes}
              />
            )}
            {puedeGestionar && <BotonBaja almacen={row.original} onError={setError} />}
          </div>
        ),
      },
    ],
    [nombreSucursal, nombreAlmacen, sucursales, almacenes, puedeGestionar],
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
      {/* El 409 de la API nombra quién se abastece de este almacén: es
          exactamente lo que hace falta para desatascarse. */}
      {error && (
        <p role="status" className="text-sm text-secondary">
          {error}
        </p>
      )}
      <TablaDatos
        columnas={columnas}
        datos={almacenes}
        placeholderBusqueda="Buscar almacén..."
      />
    </div>
  );
}
