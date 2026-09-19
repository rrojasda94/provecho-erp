import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

export const metadata: Metadata = { title: "Tu pedido" };

type ItemPedido = {
  nombre_congelado: string;
  cantidad: number;
  precio_unitario_congelado: string;
  extras: { nombre: string; cantidad: number; precio: string }[];
  valores: string[];
};

/** Lo que cuesta la línea: (producto con sabores + extras) x cantidad. */
const totalDeItem = (it: ItemPedido): number =>
  (Number(it.precio_unitario_congelado) +
    it.extras.reduce((acc, e) => acc + Number(e.precio) * e.cantidad, 0)) *
  it.cantidad;
type Pedido = {
  id: string;
  estado: "pendiente" | "confirmado" | "fallido";
  numero_orden: number | null;
  fallo_motivo: string | null;
  modalidad: string;
  medio_pago: string;
  pago_estado: "pendiente" | "aprobado" | "rechazado" | null;
  total_estimado: string;
  costo_delivery_estimado: string | null;
  eta_min: number | null;
  eta_max: number | null;
  items: ItemPedido[];
};

export default async function PedidoPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ token?: string }>;
}) {
  const { id } = await params;
  const { token } = await searchParams;
  if (!token) notFound();

  const pedido = await apiFetch<Pedido>(
    `/api/v1/storefront/publico/pedidos/${id}?token=${encodeURIComponent(token)}`,
    { revalidate: 0 },
  );
  if (!pedido) notFound();
  // Con Izipay el pedido no está confirmado hasta que se paga.
  if (pedido.estado === "pendiente" && pedido.pago_estado === "pendiente") {
    redirect(`/pedido/${id}/pago?token=${encodeURIComponent(token)}`);
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-16">
      {pedido.estado === "confirmado" && (
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="text-5xl">🍕</span>
          <h1 className="font-display text-2xl uppercase text-negro">
            ¡Pedido #{pedido.numero_orden} confirmado!
          </h1>
          {pedido.eta_min && (
            <p className="text-humo">
              Listo en {pedido.eta_min}–{pedido.eta_max} minutos.
            </p>
          )}
        </div>
      )}
      {pedido.estado === "pendiente" && (
        <div className="text-center">
          <h1 className="font-display text-2xl uppercase text-negro">Estamos confirmando tu pedido</h1>
          <p className="mt-2 text-humo">Actualiza esta página en unos segundos.</p>
        </div>
      )}
      {pedido.estado === "fallido" && (
        <div className="text-center">
          <h1 className="font-display text-2xl uppercase text-rojo">No pudimos confirmar tu pedido</h1>
          <p className="mt-2 text-humo">{pedido.fallo_motivo ?? "Intenta de nuevo."}</p>
          <Link
            href={pedido.pago_estado === "rechazado" ? "/checkout" : "/carrito"}
            className="mt-4 inline-block font-bold text-verde underline"
          >
            {pedido.pago_estado === "rechazado" ? "Intentar de nuevo" : "Volver al carrito"}
          </Link>
        </div>
      )}

      <ul className="mt-6 flex flex-col gap-2 rounded-lg border-2 border-negro bg-white p-4 text-sm">
        {pedido.items.map((it, i) => (
          <li key={i} className="flex justify-between gap-3">
            <span>
              {it.cantidad}x {it.nombre_congelado}
              {it.valores.length > 0 && (
                <span className="block text-xs text-humo">{it.valores.join(" + ")}</span>
              )}
              {it.extras.length > 0 && (
                <span className="block text-xs text-humo">
                  {it.extras.map((e) => `${e.cantidad}× ${e.nombre}`).join(" · ")}
                </span>
              )}
            </span>
            <span>S/ {totalDeItem(it).toFixed(2)}</span>
          </li>
        ))}
        {pedido.costo_delivery_estimado && (
          <li className="flex justify-between text-humo">
            <span>Delivery</span>
            <span>S/ {pedido.costo_delivery_estimado}</span>
          </li>
        )}
        <li className="flex justify-between border-t border-negro/20 pt-2 font-display text-verde">
          <span>Total</span>
          <span>S/ {pedido.total_estimado}</span>
        </li>
      </ul>
    </div>
  );
}
