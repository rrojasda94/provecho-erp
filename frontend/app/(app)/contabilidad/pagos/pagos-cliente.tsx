"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, useTransition } from "react";

import { Insignia } from "@/components/estado/insignia";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { tienePermiso } from "@/lib/permisos";

import { ejecutarPagoAction, rechazarPagoAction } from "../actions";

export type Pago = {
  id: string;
  concepto: string;
  proveedor_id: string | null;
  orden_compra_id: string | null;
  monto: string;
  monto_detraccion: string | null;
  medio_pago: string | null;
  estado: string;
  fecha_ejecucion: string | null;
  constancia: string | null;
};
export type Proveedor = {
  id: string;
  razon_social: string | null;
  persona_id: string | null;
};

/** El permiso que la API exige para ejecutar **y** para rechazar
 * (`accounting.pago_gestionar`, `accounting/api/routers.py`).
 *
 * `accounting.pago_aprobar` NO va acá aunque suene más fuerte: no gatea la
 * ruta, decide si un pago **sobre el umbral** sale derecho o queda esperando
 * firma. Esconder el botón por ese permiso le sacaría la cola de pagos al
 * contador, que paga todos los días por debajo del umbral. */
const GESTIONAR_PAGO = "accounting.pago_gestionar";

function DialogoEjecutar({ pago, proveedor }: { pago: Pago; proveedor: string }) {
  return (
    <DialogoFormulario
      titulo="Ejecutar pago"
      disparador="Ejecutar"
      claseDisparador="text-xs font-bold text-primary hover:underline"
      etiquetaEnvio="Pagar"
      etiquetaPendiente="Pagando..."
      accion={ejecutarPagoAction}
      ayuda={
        <>
          {proveedor} · S/ {pago.monto}
          {pago.monto_detraccion && Number(pago.monto_detraccion) > 0 && (
            <> · detracción S/ {pago.monto_detraccion}</>
          )}
        </>
      }
    >
      <input type="hidden" name="movimiento_id" value={pago.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Medio de pago
        <select name="medio_pago" defaultValue="transferencia">
          <option value="transferencia">Transferencia</option>
          <option value="efectivo">Efectivo</option>
          <option value="cheque">Cheque</option>
          <option value="deposito">Depósito</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Constancia
        <input name="constancia" maxLength={255} placeholder="Nº de operación, voucher..." />
      </label>
    </DialogoFormulario>
  );
}

/** Rechazar sacaba el pago de la cola sin decir nada: la acción devolvía su
 * error y el `void` lo tiraba a la basura, así que un rechazo que fallaba se
 * veía igual que uno que salió —la fila seguía ahí y nadie sabía por qué.
 * Mismo arreglo que «Anular» en la jornada de ventas. */
function BotonRechazar({ pago }: { pago: Pago }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => {
            const r = await rechazarPagoAction(pago.id);
            setError(r.error);
          })
        }
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Rechazando..." : "Rechazar"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </div>
  );
}

/** El permiso decide si la acción se ofrece, no solo el estado: la API es
 * quien autoriza de verdad, pero un botón que siempre termina en 403 es peor
 * que no tenerlo. */
function Acciones({
  pago,
  proveedor,
  permisos,
}: {
  pago: Pago;
  proveedor: string;
  permisos: string[];
}) {
  if (pago.estado !== "pendiente") {
    return <span className="text-xs text-gray">{pago.medio_pago ?? "—"}</span>;
  }
  if (!tienePermiso(permisos, GESTIONAR_PAGO)) {
    return <span className="text-xs text-gray">—</span>;
  }
  return (
    <div className="flex items-center gap-3">
      <DialogoEjecutar pago={pago} proveedor={proveedor} />
      <BotonRechazar pago={pago} />
    </div>
  );
}

export function PagosCliente({
  pagos,
  proveedores,
  permisos,
}: {
  pagos: Pago[];
  proveedores: Proveedor[];
  permisos: string[];
}) {
  const [soloPendientes, setSoloPendientes] = useState(true);
  const nombre = useMemo(
    () =>
      new Map(
        proveedores.map((p) => [p.id, p.razon_social ?? "(proveedor natural)"] as const),
      ),
    [proveedores],
  );
  const visibles = useMemo(
    () => (soloPendientes ? pagos.filter((p) => p.estado === "pendiente") : pagos),
    [pagos, soloPendientes],
  );

  const columnas: ColumnDef<Pago>[] = useMemo(
    () => [
      {
        id: "proveedor",
        header: "Proveedor",
        accessorFn: (p) =>
          (p.proveedor_id && nombre.get(p.proveedor_id)) || p.proveedor_id || "—",
      },
      { accessorKey: "concepto", header: "Concepto" },
      {
        id: "monto",
        header: "Monto",
        accessorFn: (p) => `S/ ${p.monto}`,
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          // Pendiente NO es un error: es plata que todavía se puede detener.
          // Tenía el rojo de lo destructivo y un pago aprobado se leía igual
          // que uno rechazado.
          const tono =
            estado === "ejecutado" ? "exito" : estado === "rechazado" ? "neutro" : "alerta";
          return <Insignia tono={tono}>{estado}</Insignia>;
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <Acciones
            pago={row.original}
            proveedor={
              (row.original.proveedor_id && nombre.get(row.original.proveedor_id)) ||
              "Proveedor"
            }
            permisos={permisos}
          />
        ),
      },
    ],
    [nombre, permisos],
  );

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Pagos a proveedor</h1>
      <p className="text-sm text-gray">
        La cola la llena la conformidad del comprobante en Compras: nada entra acá sin
        haberse recibido y conformado antes. Ejecutar genera el asiento contable.
      </p>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input
          type="checkbox"
          checked={soloPendientes}
          onChange={(e) => setSoloPendientes(e.target.checked)}
        />
        Solo pendientes
      </label>
      <TablaDatos columnas={columnas} datos={visibles} placeholderBusqueda="Buscar pago..." />
    </div>
  );
}
