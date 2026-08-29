"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import { abrirConteoAction } from "./actions";

export type Conteo = {
  id: string;
  almacen_id: string;
  categoria_id: string | null;
  tipo: string;
  estado: string;
  fecha_programada: string | null;
  observacion: string | null;
};

export type ProgramaConteo = {
  almacen_id: string;
  categoria_id: string;
  categoria: string;
  frecuencia: string;
  ultimo_conteo: string | null;
  proxima_fecha: string;
  estado: string;
  dias_atraso: number;
};

type Opcion = { id: string; nombre: string };

const ESTADOS = [
  ["", "Todos los estados"],
  ["abierto", "En curso"],
  ["cerrado", "Cerrados"],
  ["anulado", "Anulados"],
] as const;

export function ConteosCliente({
  conteos,
  programa,
  almacenes,
  sucursales,
  marcas,
  categorias,
  nombreDeAlmacen,
  filtros,
  permisos,
}: {
  conteos: Conteo[];
  programa: ProgramaConteo[];
  almacenes: Opcion[];
  sucursales: Opcion[];
  marcas: Opcion[];
  categorias: Opcion[];
  nombreDeAlmacen: Record<string, string>;
  filtros: { almacen: string; estado: string; sucursal: string; marca: string };
  permisos: string[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const puedeContar = tienePermiso(permisos, "inventory.contar");

  const filtrar = (campo: string, valor: string) => {
    const nuevos = new URLSearchParams(params.toString());
    if (valor) nuevos.set(campo, valor);
    else nuevos.delete(campo);
    router.push(`/inventario/conteos?${nuevos}`);
  };

  const atrasados = useMemo(
    () => programa.filter((p) => p.estado === "vencido"),
    [programa],
  );

  const columnas = useMemo<ColumnDef<Conteo>[]>(
    () => [
      {
        header: "Almacén",
        accessorFn: (c) => nombreDeAlmacen[c.almacen_id] ?? "—",
        cell: ({ row }) => (
          <Link
            href={`/inventario/conteos/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {nombreDeAlmacen[row.original.almacen_id] ?? "—"}
          </Link>
        ),
      },
      {
        header: "Alcance",
        accessorFn: (c) => (c.categoria_id ? "Una categoría" : "Todo el almacén"),
      },
      { header: "Tipo", accessorKey: "tipo" },
      { header: "Estado", accessorKey: "estado" },
      {
        header: "Programado para",
        accessorFn: (c) => c.fecha_programada ?? "—",
      },
    ],
    [nombreDeAlmacen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">
            Conteos
          </h1>
          <p className="text-xs text-gray">
            La toma de inventario. Cerrar un conteo no mueve stock: pide un
            ajuste por cada diferencia, y lo aprueba alguien más.
          </p>
        </div>
        {puedeContar && (
          <FormularioConteo almacenes={almacenes} categorias={categorias} />
        )}
      </div>

      {atrasados.length > 0 && (
        <p className="rounded-lg bg-secondary/10 px-3 py-2 text-sm text-secondary">
          {atrasados.length === 1
            ? "1 categoría se pasó de su fecha de conteo"
            : `${atrasados.length} categorías se pasaron de su fecha de conteo`}
          : {atrasados.slice(0, 4).map((p) => p.categoria).join(", ")}
          {atrasados.length > 4 ? "…" : ""}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Filtro
          etiqueta="Marca"
          valor={filtros.marca}
          opciones={marcas}
          alCambiar={(v) => filtrar("marca", v)}
        />
        <Filtro
          etiqueta="Sucursal"
          valor={filtros.sucursal}
          opciones={sucursales}
          alCambiar={(v) => filtrar("sucursal", v)}
        />
        <Filtro
          etiqueta="Almacén"
          valor={filtros.almacen}
          opciones={almacenes}
          alCambiar={(v) => filtrar("almacen", v)}
        />
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Estado
          <select
            value={filtros.estado}
            onChange={(e) => filtrar("estado", e.target.value)}
          >
            {ESTADOS.map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>
      </div>

      <TablaDatos
        columnas={columnas}
        datos={conteos}
        placeholderBusqueda="Buscar por almacén, tipo o estado..."
        vacio="No hay conteos con esos filtros."
      />
    </div>
  );
}

function Filtro({
  etiqueta,
  valor,
  opciones,
  alCambiar,
}: {
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  alCambiar: (valor: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold">
      {etiqueta}
      <Combobox
        etiqueta={etiqueta}
        marcador="Todas"
        value={valor}
        alCambiar={(v) => alCambiar(v ?? "")}
        opciones={opciones.map((o) => ({ valor: o.id, etiqueta: o.nombre }))}
      />
    </label>
  );
}

function FormularioConteo({
  almacenes,
  categorias,
}: {
  almacenes: Opcion[];
  categorias: Opcion[];
}) {
  return (
    <DialogoFormulario
      titulo="Abrir conteo"
      disparador="+ Abrir conteo"
      accion={abrirConteoAction}
      etiquetaEnvio="Abrir"
      ayuda="Al abrirlo se congela el stock esperado de cada SKU: el almacén sigue operando mientras se cuenta, y medir contra un stock que se movió inventa diferencias que nadie provocó."
      envioDeshabilitado={almacenes.length === 0}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir…"
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Qué se cuenta
        <Combobox
          name="categoria_id"
          etiqueta="Qué se cuenta"
          marcador="Todo el almacén (conteo general)"
          opciones={categorias.map((c) => ({ valor: c.id, etiqueta: c.nombre }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Tipo
        <select name="tipo" defaultValue="rutina">
          <option value="rutina">Rutina</option>
          <option value="ajuste">Ajuste</option>
          <option value="auditoria">Auditoría</option>
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Observación
        <input name="observacion" maxLength={255} placeholder="Opcional" />
      </label>
    </DialogoFormulario>
  );
}
