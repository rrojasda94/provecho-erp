import type { Metadata } from "next";

import { apiAuth, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";

import { CartaCliente, type Carta } from "./carta-cliente";

export const metadata: Metadata = {
  title: "Carta",
  description: "Pizzas, tamaños e ingredientes de Charlie's Pizzas.",
};

async function favoritosDe(token: string): Promise<string[]> {
  try {
    return await apiAuth<string[]>("/api/v1/storefront/cuentas/me/favoritos", { token });
  } catch {
    return [];
  }
}

export default async function CartaPage() {
  const sesion = await obtenerSesion();
  const [carta, favoritosIds] = await Promise.all([
    apiFetch<Carta>("/api/v1/storefront/publico/carta"),
    sesion ? favoritosDe(sesion.token) : Promise.resolve([] as string[]),
  ]);

  if (!carta || carta.productos.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <p className="text-humo">
          No pudimos cargar la carta en este momento. Vuelve a intentar en unos minutos.
        </p>
      </div>
    );
  }

  return <CartaCliente carta={carta} sesionActiva={!!sesion} favoritosIds={favoritosIds} />;
}
