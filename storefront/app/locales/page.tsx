import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";
import { configMapas } from "@/lib/mapas";

import { MapaLocales, type Sucursal } from "./mapa-locales";

export const metadata: Metadata = {
  title: "Locales",
  description: "Direcciones, teléfono y horario de los locales de Charlie's Pizzas.",
};

export default async function LocalesPage() {
  const sucursales = (await apiFetch<Sucursal[]>("/api/v1/storefront/publico/sucursales")) ?? [];
  const config = configMapas();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <h1 className="font-display text-3xl uppercase text-negro">Nuestros locales</h1>
      <MapaLocales sucursales={sucursales} apiKey={config.apiKey} mapId={config.mapId} />
    </div>
  );
}
