"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useMemo } from "react";

import { ArticuloPicker } from "@/components/articulo-picker/articulo-picker";
import { AvisoRecortado } from "@/components/estado/aviso-recortado";
import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import {
  agregarOrdenAPlanAction,
  cerrarPlanAction,
  crearPlanAction,
  iniciarPlanAction,
  type EstadoPlan,
} from "./actions";

import type { Almacen, Articulo } from "../ordenes-cliente";

export type Plan = {
  id: string;
  almacen_id: string;
  fecha: string;
  turno: string;
  linea_produccion: string;
  origen: string;
  estado: string;
};

const PRODUCIBLES: string[] = ["subreceta", "mercaderia"];

const ETIQUETA_ESTADO: Record<string, string> = {
  planificado: "Planificado",
  en_ejecucion: "En ejecución",
  cerrado: "Cerrado",
};

const ESTADO_INICIAL: EstadoPlan = { error: "", ok: false };

function comoOpciones(articulos: Articulo[]) {
  return articulos.map((a) => ({ valor: a.id, etiqueta: a.nombre, pista: a.id_interno }));
}

function DialogoNuevoPlan({ almacenes }: { almacenes: Almacen[] }) {
  return (
    <DialogoFormulario
      titulo="Nuevo plan"
      disparador="+ Nuevo plan"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearPlanAction}
      ayuda="Una línea, un turno, un día: RN-PRD-012 no deja dos planes compitiendo por la misma línea al mismo turno."
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir almacén..."
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Fecha
        <input name="fecha" type="date" required />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Turno
        <input name="turno" placeholder="mañana, tarde, noche..." maxLength={30} required />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Línea de producción
        <input
          name="linea_produccion"
          placeholder="Panadería, pastelería..."
          maxLength={100}
          required
        />
      </label>
    </DialogoFormulario>
  );
}

function DialogoAgregarOrden({ plan, articulos }: { plan: Plan; articulos: Articulo[] }) {
  const producibles = comoOpciones(articulos.filter((a) => PRODUCIBLES.includes(a.tipo)));
  return (
    <DialogoFormulario
      titulo="Agregar orden al plan"
      disparador="+ Orden"
      claseDisparador="text-xs font-bold text-primary hover:underline"
      etiquetaEnvio="Agregar"
      etiquetaPendiente="Agregando..."
      accion={agregarOrdenAPlanAction}
    >
      <input type="hidden" name="plan_id" value={plan.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué se produce
        <ArticuloPicker
          name="articulo_id"
          etiqueta="Qué se produce"
          requerido
          marcador="Elegir artículo..."
          tipos={PRODUCIBLES}
          iniciales={producibles}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad planeada
        <input name="cantidad_planeada" type="number" step="0.0001" min="0.0001" required />
      </label>
    </DialogoFormulario>
  );
}

function BotonAccionPlan({
  planId,
  accion,
  etiqueta,
  confirmacion,
}: {
  planId: string;
  accion: typeof iniciarPlanAction;
  etiqueta: string;
  confirmacion: string;
}) {
  const [estado, formAction, pendiente] = useActionState(accion, ESTADO_INICIAL);
  return (
    <form
      action={formAction}
      onSubmit={(e) => {
        if (!confirm(confirmacion)) e.preventDefault();
      }}
      className="flex flex-col gap-1"
    >
      <input type="hidden" name="plan_id" value={planId} />
      <button
        type="submit"
        disabled={pendiente}
        className="text-xs font-bold text-primary hover:underline disabled:opacity-50"
      >
        {pendiente ? "…" : etiqueta}
      </button>
      {estado.error && (
        <p role="alert" className="text-xs font-semibold text-secondary">
          {estado.error}
        </p>
      )}
    </form>
  );
}

export function PlanCliente({
  planes,
  total,
  almacenes,
  articulos,
}: {
  planes: Plan[];
  /** Cuántos hay en total: la página viene recortada. */
  total: number;
  almacenes: Almacen[];
  articulos: Articulo[];
}) {
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );

  const columnas: ColumnDef<Plan>[] = useMemo(
    () => [
      { id: "fecha", header: "Fecha", accessorKey: "fecha" },
      { id: "turno", header: "Turno", accessorKey: "turno" },
      { id: "linea", header: "Línea", accessorKey: "linea_produccion" },
      {
        id: "almacen",
        header: "Almacén",
        accessorFn: (p) => nombreAlmacen.get(p.almacen_id) ?? "—",
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          const clase =
            estado === "cerrado"
              ? "bg-gray/20 text-gray"
              : estado === "en_ejecucion"
                ? "bg-accent/30 text-dark"
                : "bg-primary/15 text-primary";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {ETIQUETA_ESTADO[estado] ?? estado}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => {
          const plan = row.original;
          if (plan.estado === "planificado") {
            return (
              <div className="flex items-center gap-3">
                <DialogoAgregarOrden plan={plan} articulos={articulos} />
                <BotonAccionPlan
                  planId={plan.id}
                  accion={iniciarPlanAction}
                  etiqueta="Iniciar"
                  confirmacion="¿Iniciar el plan? Se reservan los insumos de todas sus órdenes."
                />
              </div>
            );
          }
          if (plan.estado === "en_ejecucion") {
            return (
              <BotonAccionPlan
                planId={plan.id}
                accion={cerrarPlanAction}
                etiqueta="Cerrar"
                confirmacion="¿Cerrar el plan? Se libera lo que no se llegó a consumir."
              />
            );
          }
          return <span className="text-xs text-gray">—</span>;
        },
      },
    ],
    [almacenes, articulos, nombreAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Plan de producción</h1>
        <DialogoNuevoPlan almacenes={almacenes} />
      </div>
      <p className="text-sm text-gray">
        El cronograma fijo por línea y turno (RN-PRD-007/012): planificado → iniciado
        (reserva los insumos de sus órdenes) → cerrado (libera lo que no se consumió).
      </p>
      <AvisoRecortado
        mostrados={planes.length}
        total={total}
        sugerencia="Acota por almacén, fecha o estado para ver el resto."
      />
      <TablaDatos columnas={columnas} datos={planes} placeholderBusqueda="Buscar plan..." />
    </div>
  );
}
