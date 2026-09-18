/** Base pública del sitio (ADR-105, SEO/PR4): un solo lugar para armar URLs
 * absolutas — `sitemap.ts`, `openGraph.url`, JSON-LD. `NEXT_PUBLIC_SITE_URL`
 * cubre staging/preview; el dominio de producción es el valor por
 * defecto para que nada quede roto si la variable no está puesta. */
export const URL_SITIO =
  process.env.NEXT_PUBLIC_SITE_URL || "https://charlies.majambo.com.pe";
