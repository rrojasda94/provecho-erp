"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState, useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { cuadreDe } from "@/lib/cuadre";
import { tienePermiso } from "@/lib/permisos";

import { anularAsientoAction, crearAsientoAction } from "./actions";

export type Asiento = {
  id: string;
  fecha: string;
  glosa: string;
  origen: string;
  evento_origen: string | null;
  estado: string;
  asiento_reversa_de_id: string | null;
};
export type Cuenta = {
  id: string;
  codigo: string;
  nombre: string;
  tipo: string;
  activa: boolean;
};

/** Registrar un asiento manual y anularlo son la misma potestad para la API
 * (`accounting.asiento_manual`): anular no borra, genera el asiento inverso
 * (RN-CTB-002), o sea escribe en el libro igual que registrar. */
const ASIENTO_MANUAL = "accounting.asiento_manual";

type LineaForm = { clave: number; cuenta: string; tipo: "debe" | "haber"; monto: string };

const LINEAS_INICIALES: LineaForm[] = [
  { clave: 1, cuenta: "", tipo: "debe", monto: "" },
  { clave: 2, cuenta: "", tipo: "haber", monto: "" },
];

function DialogoNuevoAsiento({ cuentas }: { cuentas: Cuenta[] }) {
  const [lineas, setLineas] = useState<LineaForm[]>(LINEAS_INICIALES);

  // Una sola vez y no por línea: un asiento con ocho líneas recorría y
  // mapeaba el plan de cuentas ocho veces en cada tecla.
  const cuentasActivas = useMemo(
    () =>
      cuentas
        .filter((c) => c.activa)
        .map((c) => ({ valor: c.id, etiqueta: `${c.codigo} · ${c.nombre}` })),
    [cuentas],
  );

  const { debe, haber, cuadra } = cuadreDe(lineas);

  const editar = (clave: number, campo: keyof LineaForm, valor: string) =>
    setLineas((prev) =>
      prev.map((l) => (l.clave === clave ? { ...l, [campo]: valor } : l)),
    );

  return (
    <DialogoFormulario
      titulo="Asiento manual"
      disparador="+ Asiento manual"
      etiquetaEnvio="Registrar"
      etiquetaPendiente="Registrando..."
      accion={crearAsientoAction}
      ancho="max-w-2xl"
      envioDeshabilitado={!cuadra}
      // Las líneas son estado propio de la pantalla: `form.reset()` no las
      // toca porque son campos controlados. Se limpian al abrir y no al
      // cerrar para que un rechazo del servidor deje ver lo que se cargó.
      alAbrir={() => setLineas(LINEAS_INICIALES)}
    >
      <div className="flex gap-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Fecha
          <input name="fecha" type="date" required />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Glosa
          <input name="glosa" required maxLength={255} placeholder="Qué documenta el asiento" />
        </label>
      </div>

      <div className="flex flex-col gap-2">
        {lineas.map((linea) => (
          <div key={linea.clave} className="flex items-end gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs font-semibold">
              Cuenta
              <Combobox
                name="cuenta_contable_id"
                etiqueta="Cuenta"
                requerido
                marcador="Elegir cuenta..."
                value={linea.cuenta}
                alCambiar={(v) => editar(linea.clave, "cuenta", v ?? "")}
                opciones={cuentasActivas}
              />
            </label>
            <label className="flex w-28 flex-col gap-1 text-xs font-semibold">
              Tipo
              <select
                name="tipo"
                value={linea.tipo}
                onChange={(e) => editar(linea.clave, "tipo", e.target.value)}
              >
                <option value="debe">Debe</option>
                <option value="haber">Haber</option>
              </select>
            </label>
            <label className="flex w-32 flex-col gap-1 text-xs font-semibold">
              Monto
              <input
                name="monto"
                type="number"
                step="0.01"
                min="0.01"
                required
                value={linea.monto}
                onChange={(e) => editar(linea.clave, "monto", e.target.value)}
              />
            </label>
            <button
              type="button"
              aria-label="Quitar línea"
              disabled={lineas.length <= 2}
              onClick={() => setLineas((prev) => prev.filter((l) => l.clave !== linea.clave))}
              className="pb-1.5 text-muted-foreground hover:text-status-danger disabled:opacity-30"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setLineas((prev) => [
              ...prev,
              {
                clave: Math.max(...prev.map((l) => l.clave)) + 1,
                cuenta: "",
                tipo: "debe",
                monto: "",
              },
            ])
          }
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar línea
        </button>
      </div>

      {/* El cuadre en vivo (RN-CTB-001): el error más común es tipear un
          monto de más, y verlo antes de enviar ahorra el viaje. Se cuenta en
          centavos (`lib/cuadre.ts`) — comparado en flotante, 0.10 + 0.20
          contra 0.30 mostraba «Diferencia: 0.00» con el botón apagado. */}
      <div
        className={`flex justify-end gap-6 rounded px-3 py-2 text-sm font-semibold ${
          cuadra ? "bg-status-success/15 text-foreground" : "bg-status-warning/15 text-foreground"
        }`}
      >
        <span>Debe: {debe.toFixed(2)}</span>
        <span>Haber: {haber.toFixed(2)}</span>
        <span>{cuadra ? "Cuadra" : `Diferencia: ${(debe - haber).toFixed(2)}`}</span>
      </div>
    </DialogoFormulario>
  );
}

/** Anular genera el asiento inverso: nada se borra (RN-CTB-002). El error se
 * muestra bajo el botón — la acción lo devolvía y la pantalla lo descartaba,
 * así que un fallo se veía igual que un éxito. */
function BotonAnular({ asiento }: { asiento: Asiento }) {
  const [pendiente, startTransition] = useTransition();
  const [error, setError] = useState("");
  if (asiento.estado !== "registrado") {
    return <span className="text-xs text-gray">—</span>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      <button
        type="button"
        disabled={pendiente}
        onClick={() =>
          startTransition(async () => {
            const r = await anularAsientoAction(asiento.id);
            setError(r.error);
          })
        }
        title="Genera el asiento inverso (RN-CTB-002): nada se borra"
        className="text-xs font-semibold text-secondary hover:underline"
      >
        {pendiente ? "Anulando..." : "Anular"}
      </button>
      {error && <span className="text-xs text-secondary">{error}</span>}
    </div>
  );
}

export function AsientosCliente({
  asientos,
  cuentas,
  permisos,
}: {
  asientos: Asiento[];
  cuentas: Cuenta[];
  permisos: string[];
}) {
  const puedeAsentar = tienePermiso(permisos, ASIENTO_MANUAL);

  const columnas: ColumnDef<Asiento>[] = useMemo(
    () => [
      { accessorKey: "fecha", header: "Fecha" },
      { accessorKey: "glosa", header: "Glosa" },
      {
        id: "origen",
        header: "Origen",
        accessorFn: (a) => (a.origen === "automatico" ? (a.evento_origen ?? "automático") : "manual"),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          return (
            <span
              className={
                estado === "anulado"
                  ? "rounded-full bg-gray/20 px-2 py-0.5 text-xs font-semibold text-gray"
                  : "rounded-full bg-accent/30 px-2 py-0.5 text-xs font-semibold text-dark"
              }
            >
              {estado}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          puedeAsentar ? (
            <BotonAnular asiento={row.original} />
          ) : (
            <span className="text-xs text-gray">—</span>
          ),
      },
    ],
    [puedeAsentar],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Asientos</h1>
        {/* El permiso decide si la acción se ofrece: la API autoriza de
            verdad, pero un botón que siempre termina en 403 es peor que no
            tenerlo. */}
        {puedeAsentar && <DialogoNuevoAsiento cuentas={cuentas} />}
      </div>
      <p className="text-sm text-gray">
        El libro. Los asientos automáticos los genera un evento del ERP (venta, compra,
        pago); los manuales se registran acá y siempre cuadran debe contra haber.
      </p>
      {puedeAsentar && cuentas.length === 0 && (
        <p className="rounded bg-secondary/10 px-3 py-2 text-sm font-semibold text-secondary">
          No hay plan de cuentas todavía: sin cuentas no se puede registrar un asiento.
        </p>
      )}
      <TablaDatos columnas={columnas} datos={asientos} placeholderBusqueda="Buscar por glosa..." />
    </div>
  );
}
