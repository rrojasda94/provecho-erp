import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { apiFetch } from "@/lib/api";

import { PagoCliente } from "./pago-cliente";

export const metadata: Metadata = { title: "Paga tu pedido" };

type Pedido = {
  id: string;
  estado: "pendiente" | "confirmado" | "fallido";
  fallo_motivo: string | null;
  pago_estado: "pendiente" | "aprobado" | "rechazado" | null;
  pago_simulado: boolean;
  total_estimado: string;
};

export default async function PagoPage({
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
  // Ya pagado (o nada que pagar): la confirmación vive en la página del pedido.
  if (pedido.estado === "confirmado" || pedido.pago_estado === null) {
    redirect(`/pedido/${id}?token=${encodeURIComponent(token)}`);
  }

  return (
    <PagoCliente
      pedidoId={id}
      token={token}
      estado={pedido.estado}
      simulado={pedido.pago_simulado}
      total={pedido.total_estimado}
      motivo={pedido.fallo_motivo}
    />
  );
}
