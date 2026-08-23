"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useTransition } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";

import {
  crearPiezaAction,
  descartarPiezaAction,
  publicarPiezaAction,
  validarPiezaAction,
  type EstadoMarketing,
} from "../actions";
import type { Campana, Marca } from "../campanas-cliente";

export type Pieza = {
  id: string;
  campana_id: string | null;
  marca_id: string;
  titulo: string;
  canal: string;
  fecha_publicacion: string;
  pertinente_marca: boolean;
  uso_marca_validado: boolean;
  estado: string;
};

const ESTADO_INICIAL: EstadoMarketing = { error: "", ok: false };

function DialogoNuevaPieza({
  campanas,
  marcas,
}: {
  campanas: Campana[];
  marcas: Marca[];
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [estado, formAction, pendiente] = useActionState(crearPiezaAction, ESTADO_INICIAL);

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
        + Planificar pieza
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Nueva pieza</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Marca
            <select name="marca_id" required defaultValue="">
              <option value="" disabled>
                Elegir marca...
              </option>
              {marcas.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Título
            <input name="titulo" required minLength={3} maxLength={150} />
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Canal
              <input name="canal" required minLength={2} maxLength={50} placeholder="instagram" />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              Publicación
              <input name="fecha_publicacion" type="date" required />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Campaña
            <select name="campana_id" defaultValue="">
              <option value="">Sin campaña (contenido de marca)</option>
              {campanas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="flex flex-col gap-1 rounded border border-gray/20 p-3">
            <legend className="px-1 text-xs font-semibold uppercase text-gray">
              Validaciones (RN-MKT-001/002)
            </legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="pertinente_marca" />
              Pertinente a la marca
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="uso_marca_validado" />
              Uso de marca validado
            </label>
            <span className="text-xs text-gray">
              Se pueden marcar después, pero sin las dos la pieza no se publica.
            </span>
          </fieldset>
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
              {pendiente ? "Guardando..." : "Planificar"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

function SelloValidacion({
  pieza,
  campo,
  etiqueta,
}: {
  pieza: Pieza;
  campo: "pertinente_marca" | "uso_marca_validado";
  etiqueta: string;
}) {
  const [pendiente, startTransition] = useTransition();
  const valor = pieza[campo];
  const editable = pieza.estado === "planificada";
  return (
    <button
      type="button"
      disabled={pendiente || !editable}
      onClick={() => startTransition(() => void validarPiezaAction(pieza.id, campo, !valor))}
      title={editable ? `Marcar ${etiqueta}` : "Ya publicada o descartada"}
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
        valor ? "bg-accent/30 text-dark" : "bg-gray/20 text-gray"
      } ${editable ? "hover:opacity-80" : "cursor-default"}`}
    >
      {valor ? "✓" : "○"} {etiqueta}
    </button>
  );
}

function AccionesPieza({ pieza }: { pieza: Pieza }) {
  const [pendiente, startTransition] = useTransition();
  if (pieza.estado !== "planificada") return <span className="text-xs text-gray">—</span>;
  const lista = pieza.pertinente_marca && pieza.uso_marca_validado;
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        disabled={pendiente || !lista}
        onClick={() => startTransition(() => void publicarPiezaAction(pieza.id))}
        title={lista ? "Publicar" : "Faltan las dos validaciones de marca"}
        className="text-xs font-bold text-primary hover:underline disabled:opacity-40"
      >
        Publicar
      </button>
      <button
        type="button"
        disabled={pendiente}
        onClick={() => startTransition(() => void descartarPiezaAction(pieza.id))}
        className="text-xs font-semibold text-secondary hover:underline"
      >
        Descartar
      </button>
    </div>
  );
}

export function ContenidoCliente({
  piezas,
  campanas,
  marcas,
}: {
  piezas: Pieza[];
  campanas: Campana[];
  marcas: Marca[];
}) {
  const nombreCampana = useMemo(
    () => new Map(campanas.map((c) => [c.id, c.nombre])),
    [campanas],
  );

  const columnas: ColumnDef<Pieza>[] = useMemo(
    () => [
      { accessorKey: "fecha_publicacion", header: "Fecha" },
      { accessorKey: "titulo", header: "Pieza" },
      { accessorKey: "canal", header: "Canal" },
      {
        id: "campana",
        header: "Campaña",
        accessorFn: (p) =>
          p.campana_id ? (nombreCampana.get(p.campana_id) ?? "—") : "Contenido de marca",
      },
      {
        id: "validaciones",
        header: "Validaciones",
        cell: ({ row }) => (
          <div className="flex gap-1.5">
            <SelloValidacion pieza={row.original} campo="pertinente_marca" etiqueta="pertinente" />
            <SelloValidacion pieza={row.original} campo="uso_marca_validado" etiqueta="uso de marca" />
          </div>
        ),
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          const clase =
            estado === "publicada"
              ? "bg-accent/30 text-dark"
              : estado === "descartada"
                ? "bg-gray/20 text-gray"
                : "bg-cream text-dark";
          return (
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clase}`}>
              {estado}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => <AccionesPieza pieza={row.original} />,
      },
    ],
    [nombreCampana],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Contenido</h1>
        <DialogoNuevaPieza campanas={campanas} marcas={marcas} />
      </div>
      <p className="text-sm text-gray">
        Calendario de piezas, la más reciente primero. Una pieza se publica solo si es
        pertinente a la marca y su uso de marca está validado (RN-MKT-001/002) — las dos
        etiquetas se tocan para marcarlas.
      </p>
      <TablaDatos columnas={columnas} datos={piezas} placeholderBusqueda="Buscar pieza..." />
    </div>
  );
}
