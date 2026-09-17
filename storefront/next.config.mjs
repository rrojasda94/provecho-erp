/** @type {import('next').NextConfig} */
const nextConfig = {
  // Servidor autocontenido: la imagen (`storefront/Dockerfile`) copia solo
  // `.next/standalone`, sin arrastrar `node_modules` completo.
  output: "standalone",

  // Mismo motivo que `frontend/next.config.mjs`: Next 16 escribe un
  // `AGENTS.md`/`CLAUDE.md` propio en cada `next dev` si no se desactiva.
  agentRules: false,

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
