"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { InsigniaActiva } from "@/components/estado/insignia";
import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearCuentaAction, editarCuentaAction } from "../actions";
import type { Cuenta } from "../asientos-cliente";

// Los cinco del modelo contable; la naturaleza (deudora/acreedora) la deriva
// el backend del tipo, no se teclea.
const TIPOS = ["activo", "pasivo", "patrimonio", "ingreso", "gasto"] as const;

function DialogoNuevaCuenta({ cuentas }: { cuentas: Cuenta[] }) {
  return (
    <DialogoFormulario
      titulo="Nueva cuenta"
      disparador="+ Nueva cuenta"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearCuentaAction}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Código
        <input name="codigo" required maxLength={20} placeholder="ej. 42111" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue="activo">
          {TIPOS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cuenta padre
        <select name="cuenta_padre_id" defaultValue="">
          <option value="">Sin padre (cuenta de primer nivel)</option>
          {cuentas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.codigo} · {c.nombre}
            </option>
          ))}
        </select>
      </label>
    </DialogoFormulario>
  );
}

/** El código y el tipo no se editan: los asientos ya registrados apuntan a
 * esta cuenta y el tipo decide su naturaleza, o sea el signo con el que se
 * leyó todo lo asentado. Una cuenta mal creada se desactiva. */
function DialogoEditarCuenta({ cuenta }: { cuenta: Cuenta }) {
  return (
    <DialogoFormulario
      titulo={`Editar ${cuenta.codigo}`}
      disparador="Editar"
      claseDisparador={BOTON_FILA}
      accion={editarCuentaAction}
      ayuda="El código y el tipo no se cambian: los asientos ya registrados dependen de ellos. Una cuenta equivocada se desactiva."
    >
      <input type="hidden" name="id" value={cuenta.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} defaultValue={cuenta.nombre} />
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="activa" defaultChecked={cuenta.activa} />
        Activa (una cuenta inactiva no admite asientos nuevos)
      </label>
    </DialogoFormulario>
  );
}

export function PlanCuentasCliente({ cuentas }: { cuentas: Cuenta[] }) {
  const columnas: ColumnDef<Cuenta>[] = useMemo(
    () => [
      { accessorKey: "codigo", header: "Código" },
      { accessorKey: "nombre", header: "Nombre" },
      { accessorKey: "tipo", header: "Tipo" },
      {
        accessorKey: "activa",
        header: "Estado",
        cell: ({ getValue }) => <InsigniaActiva activa={getValue<boolean>()} />,
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <DialogoEditarCuenta cuenta={row.original} />,
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Plan de cuentas</h1>
        <DialogoNuevaCuenta cuentas={cuentas} />
      </div>
      <p className="text-sm text-gray">
        Las cuentas contra las que se registran los asientos. El mapeo evento → cuentas
        (venta, compra, pago) se configura por API y usa estas mismas cuentas.
      </p>
      <TablaDatos columnas={columnas} datos={cuentas} placeholderBusqueda="Buscar cuenta..." />
    </div>
  );
}
