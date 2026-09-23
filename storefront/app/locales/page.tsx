import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";
import { configMapas } from "@/lib/mapas";
import { URL_SITIO } from "@/lib/sitio";

import { MapaLocales, type Sucursal } from "./mapa-locales";

export const metadata: Metadata = {
  title: "Locales",
  description: "Direcciones, teléfono y horario de los locales de Charlie's Pizzas.",
};

function jsonLdDe(sucursales: Sucursal[]) {
  return sucursales
    .filter((s) => s.lat != null && s.lng != null)
    .map((s) => ({
      "@context": "https://schema.org",
      "@type": "Restaurant",
      name: `Charlie's Pizzas — ${s.nombre}`,
      url: URL_SITIO,
      ...(s.direccion ? { address: { "@type": "PostalAddress", streetAddress: s.direccion } } : {}),
      ...(s.telefono ? { telephone: s.telefono } : {}),
      geo: { "@type": "GeoCoordinates", latitude: s.lat, longitude: s.lng },
    }));
}

export default async function LocalesPage() {
  const sucursales = (await apiFetch<Sucursal[]>("/api/v1/storefront/publico/sucursales")) ?? [];
  const config = configMapas();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      {jsonLdDe(sucursales).map((ld, i) => (
        <script
          key={i}
          type="application/ld+json"
           
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }}
        />
      ))}
      <h1 className="font-titular text-3xl uppercase text-negro">Nuestros locales</h1>
      <MapaLocales sucursales={sucursales} apiKey={config.apiKey} mapId={config.mapId} />
    </div>
  );
}
