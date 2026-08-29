"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  avanzarCampanaAction,
  completarBriefAction,
  crearCampanaAction,
  type EstadoMarketing,
} from "./actions";
import { Combobox } from "@/components/ui/combobox";

export type Campana = {
  id: string;
  marca_id: string;
  nombre: string;
  tipo: string;
  canal: string;
  objetivo: string | null;
  publico_objetivo: string | null;
  presupuesto: string | null;
  kpi: string | null;
  estado: string;
  aprobada_por: string | null;
};
export type Marca = { id: string; nombre: string };

const ESTADO_INICIAL: EstadoMarketing = { error: "", ok: false };

const TIPOS = ["notoriedad", "impulso_venta", "lanzamiento", "medios", "evento"];

/** Los cuatro campos del brief (RN-MKT-003). Sin los cuatro la campaña no
 * se aprueba, así que la tabla necesita decir cuál falta. */
function faltantesDelBrief(c: Campana): string[] {
  const faltan: string[] = [];
  if (!c.objetivo) faltan.push("objetivo");
  if (!c.publico_objetivo) faltan.push("público");
  if (!c.presupuesto) faltan.push("presupuesto");
  if (!c.kpi) faltan.push("KPI");
  return faltan;
}

function CamposBrief({ campana }: { campana?: Campana }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Objetivo
        <input
          name="objetivo"
          maxLength={255}
          defaultValue={campana?.objetivo ?? ""}
          placeholder="Qué tiene que lograr"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Público objetivo
        <input
          name="publico_objetivo"
          maxLength={255}
          defaultValue={campana?.publico_objetivo ?? ""}
          placeholder="A quién le habla"
        />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Presupuesto
          <input
            name="presupuesto"
            type="number"
            step="0.01"
            min="0"
            defaultValue={campana?.presupuesto ?? ""}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          KPI
          <input
            name="kpi"
            maxLength={255}
            defaultValue={campana?.kpi ?? ""}
            placeholder="Cómo se mide"
          />
        </label>
      </div>
    </>
  );
}

function DialogoNuevaCampana({ marcas }: { marcas: Marca[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearCampanaAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nueva campaña
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Nueva campaña</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Marca
            <Combobox
              name="marca_id"
              etiqueta="Marca"
              requerido
              marcador="Elegir marca..."
              opciones={marcas.map((m) => ({ valor: m.id, etiqueta: m.nombre }))}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input name="nombre" required minLength={3} maxLength={120} />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Tipo
              <select name="tipo" defaultValue="impulso_venta">
                {TIPOS.map((t) => (
                  <option key={t} value={t}>
                    {t.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Canal
              <input name="canal" required minLength={2} maxLength={50} placeholder="instagram" />
            </label>
          </div>
          <p className="text-xs text-gray">
            El brief puede completarse después, pero sin sus cuatro campos la campaña no
            se aprueba ni sale a canal (RN-MKT-003).
          </p>
          <CamposBrief />
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function DialogoBrief({ campana }: { campana: Campana }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(completarBriefAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) dialogRef.current?.close();
  }, [estado.ok]);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="text-xs font-bold text-primary hover:underline"
      >
        Brief
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <input type="hidden" name="campana_id" value={campana.id} />
          <h2 className="font-heading text-lg text-dark">
            Brief · {campana.nombre}
          </h2>
          <CamposBrief campana={campana} />
          {estado.error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {estado.error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={pendiente}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
            >
              {pendiente ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function AccionesCiclo({
  campana,
  puedeAprobar,
}: {
  campana: Campana;
  puedeAprobar: boolean;
}) {
  const [pendiente, startTransition] = useTransition();
  const avanzar = (paso: "aprobacion" | "lanzamiento" | "cierre") =>
    startTransition(() => void avanzarCampanaAction(campana.id, paso));

  const faltan = faltantesDelBrief(campana);

  return (
    <div className="flex items-center gap-3">
      {campana.estado === "brief" && <DialogoBrief campana={campana} />}
      {campana.estado === "brief" && puedeAprobar && faltan.length === 0 && (
        <button
          type="button"
          disabled={pendiente}
          onClick={() => avanzar("aprobacion")}
          className="text-xs font-bold text-primary hover:underline"
        >
          Aprobar
        </button>
      )}
      {campana.estado === "aprobada" && (
        <button
          type="button"
          disabled={pendiente}
          onClick={() => avanzar("lanzamiento")}
          className="text-xs font-bold text-primary hover:underline"
        >
          Lanzar
        </button>
      )}
      {campana.estado === "en_curso" && (
        <button
          type="button"
          disabled={pendiente}
          onClick={() => avanzar("cierre")}
          className="text-xs font-semibold text-secondary hover:underline"
        >
          Cerrar
        </button>
      )}
    </div>
  );
}

export function CampanasCliente({
  campanas,
  marcas,
  puedeAprobar,
}: {
  campanas: Campana[];
  marcas: Marca[];
  puedeAprobar: boolean;
}) {
  const nombreMarca = useMemo(
    () => new Map(marcas.map((m) => [m.id, m.nombre])),
    [marcas],
  );

  const columnas: ColumnDef<Campana>[] = useMemo(
    () => [
      { accessorKey: "nombre", header: "Campaña" },
      {
        id: "marca",
        header: "Marca",
        accessorFn: (c) => nombreMarca.get(c.marca_id) ?? "—",
      },
      {
        id: "tipo",
        header: "Tipo / canal",
        accessorFn: (c) => `${c.tipo.replace("_", " ")} · ${c.canal}`,
      },
      {
        id: "brief",
        header: "Brief",
        cell: ({ row }) => {
          const faltan = faltantesDelBrief(row.original);
          return faltan.length === 0 ? (
            <span className="text-xs font-semibold text-dark">Completo</span>
          ) : (
            <span className="text-xs text-secondary">Falta {faltan.join(", ")}</span>
          );
        },
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          const clase =
            estado === "en_curso"
              ? "bg-accent/30 text-dark"
              : estado === "cerrada"
                ? "bg-gray/20 text-gray"
                : "bg-cream text-dark";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {estado.replace("_", " ")}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <AccionesCiclo campana={row.original} puedeAprobar={puedeAprobar} />
        ),
      },
    ],
    [nombreMarca, puedeAprobar],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Campañas</h1>
        <DialogoNuevaCampana marcas={marcas} />
      </div>
      <p className="text-sm text-gray">
        Brief → aprobada → en curso → cerrada. Sin objetivo, público, presupuesto y
        KPI no se aprueba; y quien redacta el brief no es quien lo aprueba (RN-MKT-003).
      </p>
      {!puedeAprobar && (
        <p className="rounded bg-cream px-3 py-2 text-xs text-gray">
          Tu usuario no aprueba campañas: eso lo hace un supervisor. Puedes armar el brief
          y dejarlas listas.
        </p>
      )}
      <TablaDatos columnas={columnas} datos={campanas} placeholderBusqueda="Buscar campaña..." />
    </div>
  );
}
