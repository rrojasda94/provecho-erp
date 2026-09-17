import type { MetadataRoute } from "next";

/** A diferencia de `clientes.majambo.com.pe` (ADR-080, `noindex`), este
 * sitio SÍ quiere indexarse: es la razón por la que ADR-103 eligió una app
 * aparte en vez de una ruta más de la landing. `sitemap.ts` completo queda
 * para PR4 (hardening/SEO); mientras tanto se permite todo. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
  };
}
