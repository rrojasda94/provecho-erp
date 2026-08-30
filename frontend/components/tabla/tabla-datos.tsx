"use client";

import {
  type ColumnDef,
  type SortingState,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";

import { Vacio } from "@/components/estado/vacio";
import { TablaBusqueda } from "@/components/tabla/tabla-busqueda";
import { TablaCuerpo } from "@/components/tabla/tabla-cuerpo";
import { TablaEncabezado } from "@/components/tabla/tabla-encabezado";
import { TablaPaginacion } from "@/components/tabla/tabla-paginacion";

/**
 * Tabla genérica del ERP (F2.11): TanStack Table headless + Tailwind. La usan
 * 28 pantallas, así que todo lo que se arregla acá se arregla 28 veces — por
 * eso la firma de props se mantiene compatible hacia atrás y lo nuevo entra
 * como opcional.
 *
 * `meta.numero` en una columna la alinea a la derecha y la pasa a cifra
 * monoespaciada tabular. Suena cosmético y no lo es: una columna de importes
 * con ancho proporcional obliga a leer dígito por dígito para comparar dos
 * filas, y comparar dos filas es a lo que se viene a un ERP.
 *
 * Repartida en cinco archivos (encabezado, cuerpo, paginación, búsqueda) por
 * el límite de complejidad del lint. La partición es deliberada, no un truco
 * para esquivarlo: cada pieza tiene un estado propio que probar.
 *
 * v2 (congelar/mover columnas, selección masiva, scroll virtual, totales) se
 * prende con las mismas APIs de TanStack cuando una pantalla lo necesite.
 */
declare module "@tanstack/react-table" {
  // Los dos parámetros no se usan acá pero no pueden renombrarse a `_TData`:
  // TypeScript solo fusiona una interfaz con la original si la lista de
  // parámetros coincide **también en los nombres**.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    /** Cifra: alinea a la derecha y aplica tabular monoespaciado. */
    numero?: boolean;
  }
}

export function TablaDatos<T>({
  columnas,
  datos,
  placeholderBusqueda = "Buscar...",
  cargando = false,
  denso = false,
  vacio,
}: {
  columnas: ColumnDef<T>[];
  datos: T[];
  placeholderBusqueda?: string;
  /** Dibuja filas fantasma en vez de una tabla en blanco. */
  cargando?: boolean;
  /** Filas más juntas: para pantallas con muchas filas por vista. */
  denso?: boolean;
  /** Qué decir cuando la consulta salió bien y no trajo filas. */
  vacio?: React.ReactNode;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filtroGlobal, setFiltroGlobal] = useState("");

  const tabla = useReactTable({
    data: datos,
    columns: columnas,
    state: { sorting, globalFilter: filtroGlobal },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFiltroGlobal,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  const sinFilas = !cargando && tabla.getRowModel().rows.length === 0;

  return (
    <div>
      <TablaBusqueda
        valor={filtroGlobal}
        alCambiar={setFiltroGlobal}
        placeholder={placeholderBusqueda}
      />

      {/* `relative` junto a `overflow-x-auto` y no por estética: un
          descendiente `position:absolute` sin ancestro posicionado toma
          como bloque contenedor el del documento, y entonces **este**
          contenedor no lo recorta. Es lo que pasa con el input oculto de
          validación que Base UI dibuja por cada `Combobox`: dentro de una
          celda quedaba a 667 px en un teléfono de 390 y estiraba la página
          entera, con la barra de scroll horizontal que eso implica. */}
      <div className="relative overflow-x-auto rounded-lg border border-border bg-card shadow-[var(--sombra-1)]">
        <table className="w-full text-sm">
          <TablaEncabezado tabla={tabla} />
          {!sinFilas && (
            <TablaCuerpo
              tabla={tabla}
              cargando={cargando}
              columnas={columnas.length}
              denso={denso}
            />
          )}
        </table>

        {sinFilas && (vacio ?? <VacioPorDefecto busqueda={filtroGlobal} />)}
      </div>

      <TablaPaginacion tabla={tabla} />
    </div>
  );
}

/** Buscar y no encontrar no es lo mismo que no tener nada: el primero se
 * resuelve borrando el filtro y el segundo dando de alta. Decirlo distinto
 * evita que alguien crea que el ERP perdió los datos. */
function VacioPorDefecto({ busqueda }: { busqueda: string }) {
  if (busqueda) {
    return (
      <Vacio
        titulo="Nada coincide con la búsqueda"
        detalle={`Ningún registro contiene «${busqueda}».`}
      />
    );
  }
  return <Vacio titulo="Todavía no hay nada acá" />;
}
