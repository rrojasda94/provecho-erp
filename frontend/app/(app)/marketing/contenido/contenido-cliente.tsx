"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useTransition } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";

import {
  crearPiezaAction,
  descartarPiezaAction,
  publicarPiezaAction,
  validarPiezaAction,
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

function DialogoNuevaPieza({
  campanas,
  marcas,
}: {
  campanas: Campana[];
  marcas: Marca[];
}) {
  return (
    <DialogoFormulario
      titulo="Nueva pieza"
      disparador="+ Planificar pieza"
      etiquetaEnvio="Planificar"
      accion={crearPiezaAction}
    >
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
        <Combobox
          name="campana_id"
          etiqueta="Campaña"
          marcador="Sin campaña (contenido de marca)"
          opciones={campanas.map((c) => ({ valor: c.id, etiqueta: c.nombre }))}
        />
      </label>
      <fieldset className="flex flex-col gap-1 rounded border border-border p-3">
        <legend className="px-1 text-xs font-semibold uppercase text-muted-foreground">
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
        <span className="text-xs text-muted-foreground">
          Se pueden marcar después, pero sin las dos la pieza no se publica.
        </span>
      </fieldset>
    </DialogoFormulario>
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
