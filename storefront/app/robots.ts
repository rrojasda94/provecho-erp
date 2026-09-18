import type { MetadataRoute } from "next";

import { URL_SITIO } from "@/lib/sitio";

/** A diferencia de `clientes.majambo.com.pe` (ADR-080, `noindex`), este
 * sitio SÍ quiere indexarse: es la razón por la que ADR-103 eligió una app
 * aparte en vez de una ruta más de la landing. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${URL_SITIO}/sitemap.xml`,
  };
}
