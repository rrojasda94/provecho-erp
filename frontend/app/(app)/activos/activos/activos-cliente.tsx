"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";

import { crearActivoAction } from "./actions";

export type Activo = {
  id: string;
  tipo: string;
  id_interno: string;
  nombre: string;
  categoria: string | null;
  estado: string;
  vehiculo: { placa: string; kilometraje_actual: number | null } | null;
};

const TIPOS_VEHICULO = ["moto", "auto", "camioneta", "camion", "otro"] as const;

function EstadoActivoInsignia({ estado }: { estado: string }) {
  if (estado === "de_baja") return <Insignia tono="neutro">De baja</Insignia>;
  if (estado === "en_mantenimiento") return <Insignia tono="alerta">En mantenimiento</Insignia>;
  return <Insignia tono="exito">Operativo</Insignia>;
}

function DialogoNuevoActivo() {
  const [tipo, setTipo] = useState<"equipamiento" | "vehiculo">("equipamiento");

  return (
    <DialogoFormulario
      titulo="Nuevo activo"
      disparador="+ Nuevo activo"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearActivoAction}
      alCerrar={() => setTipo("equipamiento")}
    >
      <div className="flex gap-4 text-sm font-semibold">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="tipo"
            value="equipamiento"
            checked={tipo === "equipamiento"}
            onChange={() => setTipo("equipamiento")}
          />
          Equipamiento
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="tipo"
            value="vehiculo"
            checked={tipo === "vehiculo"}
            onChange={() => setTipo("vehiculo")}
          />
          Vehículo
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        ID interno
        <input name="id_interno" required maxLength={8} placeholder="Hasta 8 caracteres" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Nombre
        <input name="nombre" required maxLength={150} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Categoría
        <input name="categoria" maxLength={60} placeholder="Ej. cocina, frío, reparto" />
      </label>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Marca
          <input name="marca" maxLength={60} />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
          Modelo
          <input name="modelo" maxLength={60} />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Número de serie
        <input name="numero_serie" maxLength={80} />
      </label>
      {tipo === "vehiculo" && (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Placa
            <input name="placa" required maxLength={10} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo de vehículo
            <select name="tipo_vehiculo" required defaultValue="">
              <option value="" disabled>
                Elegir…
              </option>
              {TIPOS_VEHICULO.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              N° de motor
              <input name="numero_motor" maxLength={40} />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
              N° de chasis
              <input name="numero_chasis" maxLength={40} />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tenencia
            <select name="tenencia" defaultValue="propio">
              <option value="propio">Propio</option>
              <option value="alquilado">Alquilado</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Kilometraje inicial
            <input name="kilometraje_inicial" type="number" min={0} />
          </label>
        </>
      )}
    </DialogoFormulario>
  );
}

export function ActivosCliente({ activos }: { activos: Activo[] }) {
  const columnas: ColumnDef<Activo>[] = useMemo(
    () => [
      { accessorKey: "id_interno", header: "ID" },
      { accessorKey: "nombre", header: "Nombre" },
      {
        id: "tipo",
        header: "Tipo",
        accessorFn: (a) => (a.tipo === "vehiculo" ? "Vehículo" : "Equipamiento"),
      },
      {
        id: "detalle",
        header: "Placa / categoría",
        accessorFn: (a) => a.vehiculo?.placa ?? a.categoria ?? "—",
      },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => <EstadoActivoInsignia estado={getValue<string>()} />,
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <Link
            href={`/activos/activos/${row.original.id}`}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
          >
            Ver
          </Link>
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Activos</h1>
        <DialogoNuevoActivo />
      </div>
      <TablaDatos columnas={columnas} datos={activos} placeholderBusqueda="Buscar activo..." />
    </div>
  );
}
