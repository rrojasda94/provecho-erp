import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

import { CartaCliente, type Carta } from "./carta-cliente";

export const metadata: Metadata = {
  title: "Carta",
  description: "Pizzas, tamaños e ingredientes de Charlie's Pizzas.",
};

export default async function CartaPage() {
  const carta = await apiFetch<Carta>("/api/v1/storefront/publico/carta");

  if (!carta || carta.productos.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <p className="text-humo">
          No pudimos cargar la carta en este momento. Vuelve a intentar en unos minutos.
        </p>
      </div>
    );
  }

  return <CartaCliente carta={carta} />;
}
