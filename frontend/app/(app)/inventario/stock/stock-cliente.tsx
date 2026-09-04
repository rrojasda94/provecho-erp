"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Insignia } from "@/components/estado/insignia";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { Combobox, ComboboxMultiple } from "@/components/ui/combobox";

import { declararArticulosAction } from "./actions";

export type FilaStock = {
  almacen_id: string;
  almacen: string;
  sku_id: string;
  sku_codigo: string | null;
  articulo_id: string | null;
  articulo: string | null;
  unidad: string | null;
  decimales: number | null;
  cantidad: string;
  reservado: string;
  disponible: string;
  stock_minimo: string | null;
  bajo_minimo: boolean;
};

type Opcion = { id: string; nombre: string };
export type OpcionSku = { id: string; etiqueta: string };

type Filtros = {
  almacen: string;
  sucursal: string;
  categoria: string;
  bajo: boolean;
  q: string;
};

/** Una fila del total consolidado: el mismo SKU sumado sobre sus almacenes. */
type FilaTotal = {
  sku_id: string;
  sku_codigo: string | null;
  articulo: string | null;
  unidad: string | null;
  decimales: number | null;
  almacenes: number;
  cantidad: number;
  reservado: number;
  disponible: number;
  bajo_minimo: boolean;
};

/** Con los decimales de la unidad y no con dos fijos (RN-GER-010): media
 * botella no existe y medio kilo sí, y redondear una unidad a dos decimales
 * inventa una precisión que el almacén no tiene. */
function cantidad(valor: number | string, decimales: number | null): string {
  const n = typeof valor === "number" ? valor : Number(valor);
  return n.toLocaleString("es-PE", {
    minimumFractionDigits: decimales ?? 2,
    maximumFractionDigits: decimales ?? 2,
  });
}

function consolidar(filas: FilaStock[]): FilaTotal[] {
  const por = new Map<string, FilaTotal>();
  for (const f of filas) {
    const ya = por.get(f.sku_id);
    if (ya) {
      ya.almacenes += 1;
      ya.cantidad += Number(f.cantidad);
      ya.reservado += Number(f.reservado);
      ya.disponible += Number(f.disponible);
      // Basta con que falte en un almacén: el total puede alcanzar y la
      // sucursal que lo necesita seguir sin tenerlo.
      ya.bajo_minimo ||= f.bajo_minimo;
    } else {
      por.set(f.sku_id, {
        sku_id: f.sku_id,
        sku_codigo: f.sku_codigo,
        articulo: f.articulo,
        unidad: f.unidad,
        decimales: f.decimales,
        almacenes: 1,
        cantidad: Number(f.cantidad),
        reservado: Number(f.reservado),
        disponible: Number(f.disponible),
        bajo_minimo: f.bajo_minimo,
      });
    }
  }
  return [...por.values()].sort((a, b) =>
    (a.articulo ?? "").localeCompare(b.articulo ?? ""),
  );
}

function Articulo({ id, nombre, codigo }: { id: string; nombre: string | null; codigo: string | null }) {
  return (
    <Link href={`/inventario/skus/${id}`} className="font-semibold text-primary hover:underline">
      {nombre ?? "(sin artículo)"}
      {codigo && <span className="ml-1 font-normal text-gray">· {codigo}</span>}
    </Link>
  );
}

export function StockCliente({
  filas,
  total,
  recortado,
  almacenes,
  sucursales,
  categorias,
  skus,
  puedeDeclarar,
  filtros,
}: {
  filas: FilaStock[];
  total: number;
  recortado: boolean;
  almacenes: Opcion[];
  sucursales: Opcion[];
  categorias: Opcion[];
  skus: OpcionSku[];
  puedeDeclarar: boolean;
  filtros: Filtros;
}) {
  const router = useRouter();
  const params = useSearchParams();
  // "Por almacén" es lo que se opera; "en general" es lo que se compra. El
  // reporte pedía las dos, y son la misma consulta agrupada distinto.
  const [consolidado, setConsolidado] = useState(false);

  const filtrar = (campo: string, valor: string) => {
    const nuevos = new URLSearchParams(params.toString());
    if (valor) nuevos.set(campo, valor);
    else nuevos.delete(campo);
    router.push(`/inventario/stock?${nuevos}`);
  };

  const totales = useMemo(() => consolidar(filas), [filas]);

  // "No hay stock con esos filtros" era engañoso cuando el almacén todavía no
  // maneja ningún artículo: no es que los filtros no encuentren nada, es que
  // no hay nada declarado y hasta que alguien lo declare la pantalla, el
  // conteo y el requerimiento de la jornada van a seguir vacíos.
  const sinFiltros =
    !filtros.almacen && !filtros.sucursal && !filtros.categoria && !filtros.q &&
    !filtros.bajo;
  const vacio =
    total === 0 && sinFiltros
      ? "Todavía ningún almacén maneja artículos. Empieza por agregarlos."
      : "No hay stock con esos filtros.";

  const columnasPorAlmacen = useMemo<ColumnDef<FilaStock>[]>(
    () => [
      {
        header: "Artículo",
        accessorFn: (f) => `${f.articulo ?? ""} ${f.sku_codigo ?? ""}`,
        cell: ({ row }) => (
          <Articulo
            id={row.original.sku_id}
            nombre={row.original.articulo}
            codigo={row.original.sku_codigo}
          />
        ),
      },
      { header: "Almacén", accessorKey: "almacen" },
      {
        header: "Físico",
        accessorFn: (f) => Number(f.cantidad),
        cell: ({ row }) => (
          <span className="cifra">
            {cantidad(row.original.cantidad, row.original.decimales)} {row.original.unidad ?? ""}
          </span>
        ),
      },
      {
        header: "Reservado",
        accessorFn: (f) => Number(f.reservado),
        cell: ({ row }) => (
          <span className="cifra">{cantidad(row.original.reservado, row.original.decimales)}</span>
        ),
      },
      {
        header: "Disponible",
        accessorFn: (f) => Number(f.disponible),
        cell: ({ row }) => (
          <span className="cifra font-semibold">
            {cantidad(row.original.disponible, row.original.decimales)}
          </span>
        ),
      },
      {
        header: "Mínimo",
        accessorFn: (f) => (f.stock_minimo === null ? "—" : Number(f.stock_minimo)),
        cell: ({ row }) =>
          row.original.stock_minimo === null ? (
            <span className="text-gray">—</span>
          ) : (
            <span className="cifra">
              {cantidad(row.original.stock_minimo, row.original.decimales)}
            </span>
          ),
      },
      {
        header: "Estado",
        accessorFn: (f) => (f.bajo_minimo ? "Bajo mínimo" : "Normal"),
        cell: ({ row }) =>
          row.original.bajo_minimo ? (
            <Insignia tono="peligro">Bajo mínimo</Insignia>
          ) : (
            <Insignia tono="exito">Normal</Insignia>
          ),
      },
    ],
    [],
  );

  const columnasTotal = useMemo<ColumnDef<FilaTotal>[]>(
    () => [
      {
        header: "Artículo",
        accessorFn: (f) => `${f.articulo ?? ""} ${f.sku_codigo ?? ""}`,
        cell: ({ row }) => (
          <Articulo
            id={row.original.sku_id}
            nombre={row.original.articulo}
            codigo={row.original.sku_codigo}
          />
        ),
      },
      { header: "Almacenes", accessorKey: "almacenes" },
      {
        header: "Físico",
        accessorKey: "cantidad",
        cell: ({ row }) => (
          <span className="cifra">
            {cantidad(row.original.cantidad, row.original.decimales)} {row.original.unidad ?? ""}
          </span>
        ),
      },
      {
        header: "Reservado",
        accessorKey: "reservado",
        cell: ({ row }) => (
          <span className="cifra">{cantidad(row.original.reservado, row.original.decimales)}</span>
        ),
      },
      {
        header: "Disponible",
        accessorKey: "disponible",
        cell: ({ row }) => (
          <span className="cifra font-semibold">
            {cantidad(row.original.disponible, row.original.decimales)}
          </span>
        ),
      },
      {
        header: "Estado",
        accessorFn: (f) => (f.bajo_minimo ? "Bajo en algún almacén" : "Normal"),
        cell: ({ row }) =>
          row.original.bajo_minimo ? (
            <Insignia tono="peligro">Bajo en algún almacén</Insignia>
          ) : (
            <Insignia tono="exito">Normal</Insignia>
          ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-xl italic uppercase text-dark">Stock</h1>
          <p className="text-xs text-gray">
            Qué hay y dónde. <strong>Disponible</strong> es el físico menos lo
            ya reservado: es contra ese número que se compromete stock nuevo.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-border p-0.5 text-xs font-semibold">
            {[
              [false, "Por almacén"],
              [true, "En general"],
            ].map(([valor, etiqueta]) => (
              <button
                key={String(valor)}
                type="button"
                aria-pressed={consolidado === valor}
                onClick={() => setConsolidado(valor as boolean)}
                className={`rounded-md px-3 py-1 ${
                  consolidado === valor ? "bg-primary text-primary-foreground" : "text-gray"
                }`}
              >
                {etiqueta}
              </button>
            ))}
          </div>
          {puedeDeclarar && (
            <FormularioDeclararArticulos
              almacenes={almacenes}
              skus={skus}
              almacenElegido={filtros.almacen}
            />
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
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
        <Filtro
          etiqueta="Categoría"
          valor={filtros.categoria}
          opciones={categorias}
          alCambiar={(v) => filtrar("categoria", v)}
        />
        <label className="flex items-center gap-2 pb-1 text-xs font-semibold">
          <input
            type="checkbox"
            checked={filtros.bajo}
            onChange={(e) => filtrar("bajo", e.target.checked ? "1" : "")}
          />
          Solo bajo mínimo
        </label>
      </div>

      {recortado && (
        <p className="rounded-lg bg-status-warning-surface px-3 py-2 text-sm text-status-warning">
          Se muestran {filas.length} de {total} filas. Filtra por almacén o
          categoría para ver el resto — la tabla todavía pagina del lado del
          navegador.
        </p>
      )}

      {consolidado ? (
        <TablaDatos
          columnas={columnasTotal}
          datos={totales}
          placeholderBusqueda="Buscar por artículo o SKU..."
          vacio={vacio}
        />
      ) : (
        <TablaDatos
          columnas={columnasPorAlmacen}
          datos={filas}
          placeholderBusqueda="Buscar por artículo, SKU o almacén..."
          vacio={vacio}
        />
      )}
    </div>
  );
}

/**
 * Qué artículos maneja un almacén.
 *
 * Es la acción que le faltaba a esta pantalla: hasta ahora era de solo
 * lectura sobre una tabla que solo tiene filas de lo que ya se movió, así
 * que un almacén nuevo se veía vacío y no había por dónde empezar.
 */
function FormularioDeclararArticulos({
  almacenes,
  skus,
  almacenElegido,
}: {
  almacenes: Opcion[];
  skus: OpcionSku[];
  almacenElegido: string;
}) {
  return (
    <DialogoFormulario
      titulo="Agregar artículos a un almacén"
      disparador="+ Agregar artículos"
      accion={declararArticulosAction}
      etiquetaEnvio="Agregar"
      ayuda="Declara qué maneja el almacén. Sin cantidad entran en cero, listos para contarse — que es como se carga un inventario por primera vez."
      envioDeshabilitado={almacenes.length === 0 || skus.length === 0}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Almacén
        <Combobox
          name="almacen_id"
          etiqueta="Almacén"
          requerido
          marcador="Elegir…"
          // Si la pantalla ya está filtrada por un almacén, ese es el que se
          // quiere cargar: repetir la elección es un paso de más.
          defaultValue={almacenElegido || null}
          opciones={almacenes.map((a) => ({ valor: a.id, etiqueta: a.nombre }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Artículos
        <ComboboxMultiple
          name="sku_ids"
          etiqueta="Artículos"
          requerido
          marcador="Buscar y elegir…"
          opciones={skus.map((s) => ({ valor: s.id, etiqueta: s.etiqueta }))}
        />
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cantidad inicial
        <input name="cantidad_inicial" inputMode="decimal" placeholder="Opcional: 0" />
        <span className="text-xs font-normal text-gray">
          Se aplica a todo lo elegido. Solo vale la primera vez: después,
          corregir un saldo es un ajuste y lo aprueba otro usuario.
        </span>
      </label>

      <label className="flex flex-col gap-1 text-sm font-semibold">
        Stock mínimo
        <input name="stock_minimo" inputMode="decimal" placeholder="Opcional" />
        <span className="text-xs font-normal text-gray">
          Debajo de este número el artículo entra al requerimiento de la
          jornada.
        </span>
      </label>
    </DialogoFormulario>
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
