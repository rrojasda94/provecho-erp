/** @type {import('next').NextConfig} */
const nextConfig = {
  // Servidor autocontenido: la imagen (`storefront/Dockerfile`) copia solo
  // `.next/standalone`, sin arrastrar `node_modules` completo.
  output: "standalone",

  // Mismo motivo que `frontend/next.config.mjs`: Next 16 escribe un
  // `AGENTS.md`/`CLAUDE.md` propio en cada `next dev` si no se desactiva.
  agentRules: false,

  // Fecha del build, para el "© año" del pie. Se congela acá porque las
  // páginas se revalidan cada 60 s: leer `new Date()` en tiempo de render
  // daría el año de hoy, no el de la última vez que se tocó el sitio. La
  // pasa `release.yml` como `--build-arg`; en desarrollo va vacía.
  env: { FECHA_BUILD: process.env.FECHA_BUILD ?? "" },

  images: {
    remotePatterns: process.env.STOREFRONT_IMAGENES_HOST
      ? [{ protocol: "https", hostname: process.env.STOREFRONT_IMAGENES_HOST }]
      : [],
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;
