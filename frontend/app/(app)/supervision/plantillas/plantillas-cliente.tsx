"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { BOTON_FILA, DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { InsigniaActiva } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearPlantillaAction, desactivarPlantillaAction } from "./actions";

export type Sucursal = { id: string; nombre: string };
export type Marca = { id: string; nombre: string };
export type Categoria = { id: string; nombre: string };
export type Usuario = { id: string; username: string };
export type Plantilla = {
  id: string;
  nombre: string;
  sucursal_id: string | null;
  marca_id: string | null;
  categoria_id: string;
  momento: "apertura" | "cierre";
  orden: number;
  frecuencia: "diaria" | "interdiaria" | "semanal" | "mensual";
  fecha_inicio: string;
  requiere_foto: boolean;
  activa: boolean;
};

const DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function DialogoNuevaPlantilla({
  categorias,
  sucursales,
  marcas,
  usuarios,
}: {
  categorias: Categoria[];
  sucursales: Sucursal[];
  marcas: Marca[];
  usuarios: Usuario[];
}) {
  const [alcance, setAlcance] = useState<"sucursal" | "marca">("sucursal");
  const [frecuencia, setFrecuencia] = useState("diaria");

  return (
    <DialogoFormulario
      titulo="Nueva plantilla"
      disparador="+ Nueva plantilla"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearPlantillaAction}
      ancho="max-w-lg"
    >
      <input type="hidden" name="alcance" value={alcance} />
      <div className="flex gap-4 text-sm font-semibold">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            checked={alcance === "sucursal"}
            onChange={() => setAlcance("sucursal")}
          />
          Una sucursal
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            checked={alcance === "marca"}
            onChange={() => setAlcance("marca")}
          />
          Toda una marca
        </label>
      </div>
      {alcance === "sucursal" ? (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Sucursal
          <select name="sucursal_id" required defaultValue="">
            <option value="" disabled>
              Elegir...
            </option>
            {sucursales.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nombre}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Marca
          <select name="marca_id" required defaultValue="">
            <option value="" disabled>
              Elegir...
            </option>
            {marcas.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
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
        Nombre
        <input name="nombre" required maxLength={120} />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Momento
          <select name="momento" defaultValue="apertura">
            <option value="apertura">Apertura</option>
            <option value="cierre">Cierre</option>
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Orden
          <input name="orden" type="number" min={1} defaultValue={1} />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Frecuencia
        <select
          name="frecuencia"
          value={frecuencia}
          onChange={(e) => setFrecuencia(e.target.value)}
        >
          <option value="diaria">Diaria</option>
          <option value="interdiaria">Interdiaria</option>
          <option value="semanal">Semanal</option>
          <option value="mensual">Mensual</option>
        </select>
      </label>
      {frecuencia === "semanal" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Día de la semana
          <select name="dia_semana" required defaultValue="">
            <option value="" disabled>
              Elegir...
            </option>
            {DIAS_SEMANA.map((d, i) => (
              <option key={i} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
      )}
      {frecuencia === "mensual" && (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Día del mes (1-28)
          <input name="dia_mes" type="number" min={1} max={28} required />
        </label>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Rige desde
        <input name="fecha_inicio" type="date" required />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Checklist (un ítem por línea)
        <textarea name="checklist" rows={3} required />
      </label>
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" name="requiere_foto" />
        Exige foto de evidencia
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Responsable por defecto (opcional)
        <select name="asignado_a" defaultValue="">
          <option value="">Sin asignar — se reparte cada día</option>
          {usuarios.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
      </label>
    </DialogoFormulario>
  );
}

export function PlantillasCliente({
  plantillas,
  categorias,
  sucursales,
  marcas,
  usuarios,
}: {
  plantillas: Plantilla[];
  categorias: Categoria[];
  sucursales: Sucursal[];
  marcas: Marca[];
  usuarios: Usuario[];
}) {
  const router = useRouter();
  const [pendiente, iniciarTransicion] = useTransition();

  const nombreSucursal = (id: string) => sucursales.find((s) => s.id === id)?.nombre ?? id;
  const nombreMarca = (id: string) => marcas.find((m) => m.id === id)?.nombre ?? id;

  const columnas: ColumnDef<Plantilla>[] = [
    { accessorKey: "nombre", header: "Nombre" },
    {
      id: "alcance",
      header: "Alcanza a",
      cell: ({ row }) =>
        row.original.sucursal_id
          ? nombreSucursal(row.original.sucursal_id)
          : `Marca: ${nombreMarca(row.original.marca_id!)}`,
    },
    { accessorKey: "momento", header: "Momento" },
    { accessorKey: "frecuencia", header: "Frecuencia" },
    {
      id: "activa",
      header: "Estado",
      cell: ({ row }) =>
        row.original.activa ? (
          <button
            type="button"
            disabled={pendiente}
            className={BOTON_FILA}
            onClick={() =>
              iniciarTransicion(async () => {
                await desactivarPlantillaAction(row.original.id);
                router.refresh();
              })
            }
          >
            Desactivar
          </button>
        ) : (
          <InsigniaActiva activa={false} />
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Plantillas de tarea</h1>
        <DialogoNuevaPlantilla
          categorias={categorias}
          sucursales={sucursales}
          marcas={marcas}
          usuarios={usuarios}
        />
      </div>
      <TablaDatos columnas={columnas} datos={plantillas} placeholderBusqueda="Buscar..." />
    </div>
  );
}
