"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { ArticuloPicker } from "@/components/articulo-picker/articulo-picker";
import { Combobox } from "@/components/ui/combobox";

import { CamposDeFactura } from "../ordenes-compra/[id]/orden-compra-cliente";
import type { EstadoOrdenCompra } from "../ordenes-compra/actions";
import type { Almacen, Articulo, Proveedor } from "../ordenes-compra/ordenes-compra-cliente";
import { crearCompraDirectaAction } from "./actions";

const ESTADO_INICIAL: EstadoOrdenCompra = { error: "", ok: false };

type Fila = { id: number; articuloId: string; cantidad: string; costoUnitario: string };
let siguienteId = 1;
const vacia = (): Fila => ({
  id: siguienteId++,
  articuloId: "",
  cantidad: "",
  costoUnitario: "",
});

export function CompraDirectaCliente({
  proveedores,
  almacenes,
  articulos,
  avisoArticulos,
}: {
  proveedores: Proveedor[];
  almacenes: Almacen[];
  articulos: Articulo[];
  avisoArticulos: string | null;
}) {
  const [filas, setFilas] = useState<Fila[]>([vacia()]);
  const [proveedorId, setProveedorId] = useState("");
  const [estado, formAction, pendiente] = useActionState(
    crearCompraDirectaAction,
    ESTADO_INICIAL,
  );

  const total = filas.reduce(
    (acc, f) => acc + (Number(f.cantidad) || 0) * (Number(f.costoUnitario) || 0),
    0,
  );
  const ruc = proveedores.find((p) => p.id === proveedorId)?.ruc ?? null;

  return (
    <form action={formAction} className="flex max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-heading text-xl italic uppercase text-dark">
          Compra directa
        </h1>
        <p className="text-sm text-gray">
          El gasto que ya se hizo y llega con la factura en la mano, sin orden
          previa. Se registra como una orden de compra ya recibida y conforme,
          así que entra stock y encola el pago igual que cualquier otra.
        </p>
      </header>

      {articulos.length === 0 && (
        <p className="text-sm text-secondary">
          {avisoArticulos ??
            "No hay artículos en el catálogo — crea uno en Inventario antes de registrar una compra."}
        </p>
      )}

      <section className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Proveedor
          <Combobox
            name="proveedor_id"
            etiqueta="Proveedor"
            requerido
            marcador="Elegir..."
            value={proveedorId}
            alCambiar={(v) => setProveedorId(v ?? "")}
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
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-gray">Qué se compró</h2>
        {filas.map((fila) => (
          <div key={fila.id} className="grid grid-cols-[1fr_5rem_6rem_auto] items-center gap-2">
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
              alCambiar={(v) =>
                setFilas((fs) =>
                  fs.map((f) => (f.id === fila.id ? { ...f, articuloId: v ?? "" } : f)),
                )
              }
            />
            <input
              name="cantidad[]"
              type="number"
              min="0.0001"
              step="0.0001"
              placeholder="Cant."
              value={fila.cantidad}
              onChange={(e) =>
                setFilas((fs) =>
                  fs.map((f) => (f.id === fila.id ? { ...f, cantidad: e.target.value } : f)),
                )
              }
              required
            />
            <input
              name="costo_unitario[]"
              type="number"
              min="0"
              step="0.0001"
              placeholder="Costo"
              value={fila.costoUnitario}
              onChange={(e) =>
                setFilas((fs) =>
                  fs.map((f) =>
                    f.id === fila.id ? { ...f, costoUnitario: e.target.value } : f,
                  ),
                )
              }
              required
            />
            <button
              type="button"
              onClick={() => setFilas((fs) => fs.filter((f) => f.id !== fila.id))}
              disabled={filas.length === 1}
              aria-label="Quitar ítem"
              className="rounded border border-gray px-2 py-1 text-sm text-gray disabled:opacity-30"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setFilas((fs) => [...fs, vacia()])}
          className="self-start text-sm font-semibold text-primary hover:underline"
        >
          + Agregar ítem
        </button>
        <p className="text-right text-sm font-semibold text-gray">
          Costo de lo comprado: S/ {total.toFixed(2)}
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-bold uppercase text-gray">La factura</h2>
        <CamposDeFactura rucSugerido={ruc} />
      </section>

      {estado.error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {estado.error}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Link
          href="/compras/ordenes-compra"
          className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
        >
          Cancelar
        </Link>
        <button
          type="submit"
          disabled={pendiente || articulos.length === 0}
          className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
        >
          {pendiente ? "Registrando…" : "Registrar la compra"}
        </button>
      </div>
    </form>
  );
}
