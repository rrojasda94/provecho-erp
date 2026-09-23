import type { MetadataRoute } from "next";

import { apiFetch } from "@/lib/api";
import { URL_SITIO } from "@/lib/sitio";

type Producto = { id: string };
type Carta = { productos: Producto[] };

/** Páginas estáticas + una entrada por producto de la carta — no hay
 * sucursal ni ingrediente en la lista: son detalle de una página que ya
 * está indexada (la carta), no una entrada propia que valga la pena que
 * Google rastree por separado. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const carta = await apiFetch<Carta>("/api/v1/storefront/publico/carta");

  const estaticas: MetadataRoute.Sitemap = [
    { url: URL_SITIO, changeFrequency: "daily", priority: 1 },
    { url: `${URL_SITIO}/carta`, changeFrequency: "daily", priority: 0.9 },
    { url: `${URL_SITIO}/locales`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${URL_SITIO}/nosotros`, changeFrequency: "monthly", priority: 0.4 },
    {
      url: `${URL_SITIO}/trabaja-con-nosotros`,
      changeFrequency: "weekly",
      priority: 0.3,
    },
  ];

  const productos: MetadataRoute.Sitemap = (carta?.productos ?? []).map((p) => ({
    url: `${URL_SITIO}/carta/${p.id}`,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...estaticas, ...productos];
}
