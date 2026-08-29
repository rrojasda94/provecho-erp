"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useActionState, useEffect, useMemo, useRef, useState } from "react";

import { TablaDatos } from "@/components/tabla/tabla-datos";
import { pedir } from "@/lib/cliente-api";

import { crearOrdenCompraAction, editarOrdenCompraAction, type EstadoOrdenCompra } from "./actions";

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
  almacen_destino_id: string;
  estado: string;
  total: string;
  items?: OrdenCompraItem[];
};
export type Proveedor = { id: string; razon_social: string | null; ruc: string | null };
export type Almacen = { id: string; nombre: string; tipo: string };
export type Articulo = { id: string; id_interno: string; nombre: string };

const ESTADO_INICIAL: EstadoOrdenCompra = { error: "", ok: false };

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
      <select
        name="articulo_id[]"
        value={fila.articuloId}
        onChange={(e) => onCambiar("articuloId", e.target.value)}
        required
      >
        <option value="" disabled>
          Artículo...
        </option>
        {articulos.map((a) => (
          <option key={a.id} value={a.id}>
            {a.id_interno} — {a.nombre}
          </option>
        ))}
      </select>
      <input
        name="cantidad[]"
        type="number"
        min="0.01"
        step="0.01"
        placeholder="Cant."
        value={fila.cantidad}
        onChange={(e) => onCambiar("cantidad", e.target.value)}
        required
      />
      <input
        name="costo_unitario[]"
        type="number"
        min="0"
        step="0.01"
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

function DialogoNuevaOC({
  proveedores,
  almacenes,
  articulos,
}: {
  proveedores: Proveedor[];
  almacenes: Almacen[];
  articulos: Articulo[];
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [filas, setFilas] = useState<Fila[]>([filaVacia()]);
  const [estado, formAction, pendiente] = useActionState(crearOrdenCompraAction, ESTADO_INICIAL);

  useEffect(() => {
    if (estado.ok) {
      formRef.current?.reset();
      setFilas([filaVacia()]);
      dialogRef.current?.close();
    }
  }, [estado.ok]);

  const total = filas.reduce(
    (acc, f) => acc + (Number(f.cantidad) || 0) * (Number(f.costoUnitario) || 0),
    0,
  );

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        disabled={articulos.length === 0}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
      >
        + Nueva orden de compra
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-2xl rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => {
          formRef.current?.reset();
          setFilas([filaVacia()]);
        }}
      >
        <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">
            Nueva orden de compra
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Proveedor
              <select name="proveedor_id" required defaultValue="">
                <option value="" disabled>
                  Elegir...
                </option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.razon_social ?? p.ruc}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Almacén destino
              <select name="almacen_destino_id" required defaultValue="">
                <option value="" disabled>
                  Elegir...
                </option>
                {almacenes.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre} ({a.tipo})
                  </option>
                ))}
              </select>
            </label>
          </div>

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
                  setFilas((fs) =>
                    fs.map((f) => (f.id === fila.id ? { ...f, [campo]: valor } : f)),
                  )
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

          <p className="text-right text-sm font-semibold text-gray">
            Total estimado: S/ {total.toFixed(2)}
          </p>

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
              {pendiente ? "Creando..." : "Crear (borrador)"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}

const ESTADO_EDICION_INICIAL: EstadoOrdenCompra = { error: "", ok: false };

/** OC en borrador es editable (precio/cantidad); desde `emitida` es
 * inmutable. El detalle con ítems se pide recién al abrir el diálogo — la
 * tabla no los trae para no pedir N detalles por cada fila listada. */
function BotonEditarOC({ orden, articulos }: { orden: OrdenCompra; articulos: Articulo[] }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [filas, setFilas] = useState<Fila[]>([]);
  const [cargando, setCargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState("");
  const [estado, formAction, pendiente] = useActionState(
    editarOrdenCompraAction,
    ESTADO_EDICION_INICIAL,
  );

  useEffect(() => {
    if (estado.ok) dialogRef.current?.close();
  }, [estado.ok]);

  async function abrir() {
    setErrorCarga("");
    setCargando(true);
    dialogRef.current?.showModal();
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
      setErrorCarga("No se pudo cargar el detalle de la orden.");
    } finally {
      setCargando(false);
    }
  }

  const total = filas.reduce(
    (acc, f) => acc + (Number(f.cantidad) || 0) * (Number(f.costoUnitario) || 0),
    0,
  );

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className="text-sm font-semibold text-primary hover:underline"
      >
        Editar
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-2xl rounded-lg p-0 backdrop:bg-dark/40"
        onClose={() => formRef.current?.reset()}
      >
        {cargando ? (
          <p className="p-6 text-sm text-gray">Cargando...</p>
        ) : (
          <form ref={formRef} action={formAction} className="flex flex-col gap-4 p-6">
            <h2 className="font-heading text-lg text-dark">Editar orden de compra (borrador)</h2>
            <input type="hidden" name="orden_id" value={orden.id} />

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
                    setFilas((fs) =>
                      fs.map((f) => (f.id === fila.id ? { ...f, [campo]: valor } : f)),
                    )
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

            <p className="text-right text-sm font-semibold text-gray">
              Total estimado: S/ {total.toFixed(2)}
            </p>

            {(errorCarga || estado.error) && (
              <p role="alert" className="text-sm font-semibold text-secondary">
                {errorCarga || estado.error}
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
                disabled={pendiente || filas.length === 0}
                className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
              >
                {pendiente ? "Guardando..." : "Guardar cambios"}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </>
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

  const columnas: ColumnDef<OrdenCompra>[] = useMemo(
    () => [
      {
        id: "proveedor",
        header: "Proveedor",
        accessorFn: (o) => nombreProveedor.get(o.proveedor_id) ?? "—",
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Órdenes de compra</h1>
        <DialogoNuevaOC proveedores={proveedores} almacenes={almacenes} articulos={articulos} />
      </div>
      {articulos.length === 0 && (
        <p className="text-sm text-secondary">
          {avisoArticulos ??
            "No hay artículos en el catálogo — crea uno en Inventario antes de emitir una OC."}
        </p>
      )}
      <TablaDatos columnas={columnas} datos={ordenes} placeholderBusqueda="Buscar orden..." />
    </div>
  );
}
