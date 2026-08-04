/** @type {import('next').NextConfig} */
const nextConfig = {
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
