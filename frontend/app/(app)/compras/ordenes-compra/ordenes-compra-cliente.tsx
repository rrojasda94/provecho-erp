"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { pedir } from "@/lib/cliente-api";

import { crearOrdenCompraAction, editarOrdenCompraAction } from "./actions";
import { ArticuloPicker } from "@/components/articulo-picker/articulo-picker";
import { Combobox } from "@/components/ui/combobox";

export type OrdenCompraItem = {
  id: string;
  articulo_id: string;
  cantidad: string;
  costo_unitario: string;
  cantidad_recibida: string;
};
export type OrdenCompra = {
  id: string;
  proveedor_id: string;
  tipo: string;
  // `oc` | `directa` (ADR-082). Se listan juntas y se distinguen acá.
  origen: string;
  almacen_destino_id: string;
  estado: string;
  total: string;
  items?: OrdenCompraItem[];
};
export type Proveedor = { id: string; razon_social: string | null; ruc: string | null };
export type Almacen = { id: string; nombre: string; tipo: string };
export type Articulo = {
  id: string;
  id_interno: string;
  nombre: string;
  // Decide si la recepción pide lote y vencimiento (RN-VNC-002).
  controla_lote: boolean;
};

const ESTILO_ESTADO: Record<string, string> = {
  borrador: "bg-gray/20 text-gray",
  emitida: "bg-accent/30 text-dark",
  recibida_parcial: "bg-accent/30 text-dark",
  recibida: "bg-accent/50 text-dark",
  anulada: "bg-secondary/20 text-secondary",
};

type Fila = { id: number; articuloId: string; cantidad: string; costoUnitario: string };
let siguienteFilaId = 1;
const filaVacia = (): Fila => ({ id: siguienteFilaId++, articuloId: "", cantidad: "", costoUnitario: "" });

function FilaItem({
  fila,
  articulos,
  onCambiar,
  onQuitar,
  puedeQuitar,
}: {
  fila: Fila;
  articulos: Articulo[];
  onCambiar: (campo: keyof Omit<Fila, "id">, valor: string) => void;
  onQuitar: () => void;
  puedeQuitar: boolean;
}) {
  return (
    <div className="grid grid-cols-[1fr_5rem_6rem_auto] items-center gap-2">
      <ArticuloPicker
        name="articulo_id[]"
        etiqueta="Artículo"
        requerido
        marcador="Artículo..."
        iniciales={articulos.map((a) => ({
          valor: a.id,
          etiqueta: a.nombre,
          pista: a.id_interno,
        }))}
        value={fila.articuloId}
        alCambiar={(v) => onCambiar("articuloId", v ?? "")}
      />
      <input
        name="cantidad[]"
        type="number"
        min="0.0001"
        step="0.0001"
        placeholder="Cant."
        value={fila.cantidad}
        onChange={(e) => onCambiar("cantidad", e.target.value)}
        required
      />
      <input
        name="costo_unitario[]"
        type="number"
        min="0"
        step="0.0001"
        placeholder="Costo"
        value={fila.costoUnitario}
        onChange={(e) => onCambiar("costoUnitario", e.target.value)}
        required
      />
      <button
        type="button"
        onClick={onQuitar}
        disabled={!puedeQuitar}
        aria-label="Quitar ítem"
        className="rounded border border-gray px-2 py-1 text-sm text-gray disabled:opacity-30"
      >
        ✕
      </button>
    </div>
  );
}

/** Los ítems de una OC, con su total en vivo. Es el mismo bloque en el alta y
 * en la corrección, y sin él cada diálogo repetía las filas, el botón de
 * agregar y el cálculo. */
function ItemsDeOrden({
  filas,
  setFilas,
  articulos,
}: {
  filas: Fila[];
  setFilas: React.Dispatch<React.SetStateAction<Fila[]>>;
  articulos: Articulo[];
}) {
  const total = filas.reduce(
    (acc, f) => acc + (Number(f.cantidad) || 0) * (Number(f.costoUnitario) || 0),
    0,
  );
  return (
    <>
      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold">Ítems</span>
        {filas.map((fila) => (
          <FilaItem
            key={fila.id}
            fila={fila}
            articulos={articulos}
            puedeQuitar={filas.length > 1}
            onQuitar={() => setFilas((fs) => fs.filter((f) => f.id !== fila.id))}
            onCambiar={(campo, valor) =>
              setFilas((fs) => fs.map((f) => (f.id === fila.id ? { ...f, [campo]: valor } : f)))
            }
          />
        ))}
        <button
          type="button"
          onClick={() => setFilas((fs) => [...fs, filaVacia()])}
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar ítem
        </button>
      </div>
      <p className="text-right text-sm font-semibold text-muted-foreground">
        Total estimado: S/ {total.toFixed(2)}
      </p>
    </>
  );
}

function DialogoNuevaOC({
  proveedores,
  almacenes,
  articulos,
}: {
  proveedores: Proveedor[];
  almacenes: Almacen[];
  articulos: Articulo[];
}) {
  const [filas, setFilas] = useState<Fila[]>([filaVacia()]);

  return (
    <DialogoFormulario
      titulo="Nueva orden de compra"
      disparador="+ Nueva orden de compra"
      etiquetaEnvio="Crear (borrador)"
      etiquetaPendiente="Creando..."
      accion={crearOrdenCompraAction}
      ancho="max-w-2xl"
      envioDeshabilitado={articulos.length === 0}
      // Las filas son campos controlados: `form.reset()` no las toca.
      alAbrir={() => setFilas([filaVacia()])}
    >
      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Proveedor
          <Combobox
            name="proveedor_id"
            etiqueta="Proveedor"
            requerido
            marcador="Elegir..."
            opciones={proveedores.map((p) => ({
              valor: p.id,
              etiqueta: p.razon_social ?? p.ruc ?? "",
              pista: p.razon_social ? (p.ruc ?? undefined) : undefined,
            }))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Almacén destino
          <Combobox
            name="almacen_destino_id"
            etiqueta="Almacén destino"
            requerido
            marcador="Elegir..."
            opciones={almacenes.map((a) => ({
              valor: a.id,
              etiqueta: a.nombre,
              pista: a.tipo,
            }))}
          />
        </label>
      </div>
      <ItemsDeOrden filas={filas} setFilas={setFilas} articulos={articulos} />
    </DialogoFormulario>
  );
}

/** OC en borrador es editable (precio/cantidad); desde `emitida` es
 * inmutable. El detalle con ítems se pide recién **antes de abrir** — la
 * tabla no los trae para no pedir N detalles por cada fila listada, y abrir
 * primero mostraba un formulario vacío que se llenaba solo un segundo
 * después. */
function BotonEditarOC({ orden, articulos }: { orden: OrdenCompra; articulos: Articulo[] }) {
  const [filas, setFilas] = useState<Fila[]>([]);
  const [errorCarga, setErrorCarga] = useState("");

  async function cargar() {
    setErrorCarga("");
    try {
      const detalle = await pedir<OrdenCompra>(`/purchases/ordenes-compra/${orden.id}`);
      setFilas(
        (detalle.items ?? []).map((it) => ({
          id: siguienteFilaId++,
          articuloId: it.articulo_id,
          cantidad: it.cantidad,
          costoUnitario: it.costo_unitario,
        })),
      );
    } catch {
      setFilas([]);
      setErrorCarga("No se pudo cargar el detalle de la orden.");
    }
  }

  return (
    <DialogoFormulario
      titulo="Editar orden de compra (borrador)"
      disparador="Editar"
      claseDisparador="text-sm font-semibold text-primary hover:underline"
      etiquetaEnvio="Guardar cambios"
      accion={editarOrdenCompraAction}
      ancho="max-w-2xl"
      envioDeshabilitado={filas.length === 0}
      alAbrir={cargar}
    >
      <input type="hidden" name="orden_id" value={orden.id} />
      {errorCarga && (
        <p role="alert" className="text-sm font-semibold text-status-danger">
          {errorCarga}
        </p>
      )}
      <ItemsDeOrden filas={filas} setFilas={setFilas} articulos={articulos} />
    </DialogoFormulario>
  );
}

export function OrdenesCompraCliente({
  ordenes,
  proveedores,
  almacenes,
  articulos,
  avisoArticulos,
}: {
  ordenes: OrdenCompra[];
  proveedores: Proveedor[];
  almacenes: Almacen[];
  articulos: Articulo[];
  avisoArticulos?: string | null;
}) {
  const nombreProveedor = useMemo(
    () => new Map(proveedores.map((p) => [p.id, p.razon_social ?? p.ruc ?? "—"])),
    [proveedores],
  );
  const nombreAlmacen = useMemo(
    () => new Map(almacenes.map((a) => [a.id, a.nombre])),
    [almacenes],
  );
  // Se filtra en el cliente y no por URL: el listado ya viene entero y son
  // dos valores, no un catálogo. Mismo patrón que Contabilidad → Pagos.
  const [origen, setOrigen] = useState("");

  const columnas: ColumnDef<OrdenCompra>[] = useMemo(
    () => [
      {
        id: "proveedor",
        header: "Proveedor",
        accessorFn: (o) => nombreProveedor.get(o.proveedor_id) ?? "—",
        // La fila abre la ficha, que es donde la OC se emite, se recibe y se
        // factura. Antes el listado era el final del camino.
        cell: ({ row }) => (
          <Link
            href={`/compras/ordenes-compra/${row.original.id}`}
            className="font-semibold text-primary hover:underline"
          >
            {nombreProveedor.get(row.original.proveedor_id) ?? "—"}
          </Link>
        ),
      },
      {
        id: "origen",
        header: "Origen",
        accessorFn: (o) => (o.origen === "directa" ? "Compra directa" : "OC"),
      },
      {
        id: "almacen",
        header: "Destino",
        accessorFn: (o) => nombreAlmacen.get(o.almacen_destino_id) ?? "—",
      },
      { accessorKey: "tipo", header: "Tipo" },
      { accessorKey: "total", header: "Total" },
      {
        accessorKey: "estado",
        header: "Estado",
        cell: ({ getValue }) => {
          const estado = getValue<string>();
          return (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ESTILO_ESTADO[estado] ?? "bg-gray/20 text-gray"}`}
            >
              {estado.replace("_", " ")}
            </span>
          );
        },
      },
      {
        id: "acciones",
        header: "",
        cell: ({ row }) =>
          row.original.estado === "borrador" ? (
            <BotonEditarOC orden={row.original} articulos={articulos} />
          ) : null,
      },
    ],
    [nombreProveedor, nombreAlmacen, articulos],
  );

  const visibles = useMemo(
    () => (origen ? ordenes.filter((o) => o.origen === origen) : ordenes),
    [ordenes, origen],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-heading text-xl text-dark">Órdenes de compra</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/compras/directas"
            className="rounded border border-primary px-4 py-2 text-sm font-bold text-primary hover:bg-primary/10"
          >
            Compra directa
          </Link>
          <DialogoNuevaOC proveedores={proveedores} almacenes={almacenes} articulos={articulos} />
        </div>
      </div>
      {articulos.length === 0 && (
        <p className="text-sm text-secondary">
          {avisoArticulos ??
            "No hay artículos en el catálogo — crea uno en Inventario antes de emitir una OC."}
        </p>
      )}
      <label className="flex w-52 flex-col gap-1 text-xs font-semibold">
        Origen
        <select value={origen} onChange={(e) => setOrigen(e.target.value)}>
          <option value="">Todas</option>
          <option value="oc">Órdenes de compra</option>
          <option value="directa">Compras directas</option>
        </select>
      </label>
      <TablaDatos columnas={columnas} datos={visibles} placeholderBusqueda="Buscar orden..." />
    </div>
  );
}
