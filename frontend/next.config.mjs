/** @type {import('next').NextConfig} */
const nextConfig = {
  // Next 16 escribe `AGENTS.md` y un `CLAUDE.md` que lo incluye cada vez que
  // corre `next dev`. `CLAUDE.md` es un archivo de reglas del proyecto que se
  // redacta a mano y que Claude Code carga como instrucciones: que una
  // dependencia lo genere sola convierte una actualización de `next` en un
  // cambio de las reglas con las que se trabaja, sin que nadie lo revise.
  // Además ensucia el árbol en cada arranque. La documentación de Next 16
  // sigue disponible en `node_modules/next/dist/docs/`.
  agentRules: false,

  // Cabeceras que no dependen del contenido. La CSP no está acá porque
  // lleva un nonce por request — se arma en `middleware.ts`.
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
