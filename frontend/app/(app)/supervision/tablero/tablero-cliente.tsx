"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { asignarAction, crearTareaManualAction, generarDiaAction } from "./actions";

export type Sucursal = { id: string; nombre: string };
export type Categoria = { id: string; nombre: string };
export type Usuario = { id: string; username: string };
export type TareaInstancia = {
  id: string;
  momento: "apertura" | "cierre";
  orden: number;
  nombre: string;
  categoria_id: string;
  asignado_a: string | null;
  estado: "pendiente" | "completada" | "vencida";
  tiene_foto: boolean;
  foto_valida: boolean | null;
};

function InsigniaEstado({ estado }: { estado: TareaInstancia["estado"] }) {
  if (estado === "completada") return <Insignia tono="exito">Completada</Insignia>;
  if (estado === "vencida") return <Insignia tono="peligro">Vencida</Insignia>;
  return <Insignia tono="neutro">Pendiente</Insignia>;
}

function DialogoNuevaTarea({
  sucursalActual,
  fechaActual,
  categorias,
}: {
  sucursalActual: string;
  fechaActual: string;
  categorias: Categoria[];
}) {
  return (
    <DialogoFormulario
      titulo="Tarea manual"
      disparador="+ Tarea manual"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearTareaManualAction}
      ayuda="Para un imprevisto del día que no amerita una plantilla permanente."
    >
      <input type="hidden" name="sucursal_id" value={sucursalActual} />
      <input type="hidden" name="fecha" value={fechaActual} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={120} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Categoría
        <select name="categoria_id" required defaultValue="">
          <option value="" disabled>
            Elegir...
          </option>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Momento
        <select name="momento" defaultValue="apertura">
          <option value="apertura">Apertura</option>
          <option value="cierre">Cierre</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Checklist (un ítem por línea)
        <textarea name="checklist" rows={3} required />
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="requiere_foto" />
        Exige foto de evidencia
      </label>
    </DialogoFormulario>
  );
}

function SelectorAsignado({
  tarea,
  usuarios,
}: {
  tarea: TareaInstancia;
  usuarios: Usuario[];
}) {
  const router = useRouter();
  const [pendiente, iniciarTransicion] = useTransition();

  return (
    <select
      className="text-xs"
      value={tarea.asignado_a ?? ""}
      disabled={pendiente}
      onChange={(e) =>
        iniciarTransicion(async () => {
          await asignarAction(tarea.id, e.target.value);
          router.refresh();
        })
      }
    >
      <option value="" disabled>
        Sin asignar
      </option>
      {usuarios.map((u) => (
        <option key={u.id} value={u.id}>
          {u.username}
        </option>
      ))}
    </select>
  );
}

/** Tablero del supervisor: todas las tareas de una sucursal en un día, con
 * estado, responsable y evidencia — `supervision.gestionar`. */
export function TableroCliente({
  tareas,
  error,
  sucursales,
  sucursalActual,
  fechaActual,
  categorias,
  usuarios,
}: {
  tareas: TareaInstancia[];
  error: string | null;
  sucursales: Sucursal[];
  sucursalActual: string;
  fechaActual: string;
  categorias: Categoria[];
  usuarios: Usuario[];
}) {
  const router = useRouter();
  const [generando, setGenerando] = useState(false);
  const [avisoGenerar, setAvisoGenerar] = useState("");

  function cambiarFiltro(sucursal: string, fecha: string) {
    router.push(`/supervision/tablero?sucursal=${sucursal}&fecha=${fecha}`);
  }

  async function generarDia() {
    setGenerando(true);
    setAvisoGenerar("");
    const r = await generarDiaAction(fechaActual);
    setGenerando(false);
    setAvisoGenerar(r.ok ? `${r.generadas} tarea(s) generada(s).` : r.error);
    router.refresh();
  }

  const columnas: ColumnDef<TareaInstancia>[] = [
    { accessorKey: "momento", header: "Momento" },
    { accessorKey: "orden", header: "Orden" },
    { accessorKey: "nombre", header: "Tarea" },
    {
      id: "estado",
      header: "Estado",
      cell: ({ row }) => <InsigniaEstado estado={row.original.estado} />,
    },
    {
      id: "asignado",
      header: "Asignado a",
      cell: ({ row }) => <SelectorAsignado tarea={row.original} usuarios={usuarios} />,
    },
    {
      id: "foto",
      header: "Foto",
      cell: ({ row }) =>
        row.original.tiene_foto ? (row.original.foto_valida === false ? "⚠️" : "✓") : "—",
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="font-heading text-xl text-dark">Tablero de supervisión</h1>
        <div className="flex items-center gap-2">
          <DialogoNuevaTarea
            sucursalActual={sucursalActual}
            fechaActual={fechaActual}
            categorias={categorias}
          />
          <button
            type="button"
            onClick={generarDia}
            disabled={generando}
            className={BOTON_FILA}
          >
            {generando ? "Generando..." : "Generar día"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <select
          value={sucursalActual}
          onChange={(e) => cambiarFiltro(e.target.value, fechaActual)}
        >
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nombre}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={fechaActual}
          onChange={(e) => cambiarFiltro(sucursalActual, e.target.value)}
        />
      </div>

      {avisoGenerar && <p className="text-sm text-gray">{avisoGenerar}</p>}
      {error ? (
        <p className="text-secondary">{error}</p>
      ) : (
        <TablaDatos columnas={columnas} datos={tareas} placeholderBusqueda="Buscar tarea..." />
      )}
    </div>
  );
}
