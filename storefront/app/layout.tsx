import localFont from "next/font/local";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";
import { configMapas } from "@/lib/mapas";
import { URL_SITIO } from "@/lib/sitio";
import { CarritoBadge } from "@/components/carrito-badge";
import { ProveedorConfigMapas } from "@/components/direccion/config-mapas";
import { RevelarObservador } from "@/components/revelar-observador";

import "./globals.css";

// Tusker Grotesk, la tipografía principal del brandbook (p. 47-49): el corte 4500
// Medium y el 5800 Super. Se sirven desde el propio sitio (`next/font/local`):
// sin pedirle nada a Google, con precarga y sin salto de diseño. Ya no lleva el
// cuerpo de texto — ver el comentario de `--fuente-cuerpo` en `globals.css`.
const tusker = localFont({
  src: [
    { path: "./fonts/TuskerGrotesk-4500Medium.woff2", weight: "400 500", style: "normal" },
    { path: "./fonts/TuskerGrotesk-5800Super.woff2", weight: "600 900", style: "normal" },
  ],
  variable: "--fuente-tusker",
  display: "swap",
  fallback: ["Arial Narrow", "system-ui", "sans-serif"],
});

// Isidora Black 7800, la de titulares del brandbook (p. 49). Solo llegó este
// corte, así que se usa donde corresponde un peso así: el título grande de cada
// página. No sirve para párrafos — un texto entero en negra 900 cansa más que
// la condensada que veníamos usando.
const isidora = localFont({
  src: [{ path: "./fonts/isidora-black.woff2", weight: "900", style: "normal" }],
  variable: "--fuente-isidora",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

/** Año de la última actualización del sitio. Lo inyecta el build (`FECHA_BUILD`,
 * ver `Dockerfile` y `next.config.mjs`); en desarrollo, el año de hoy. */
function anioDeActualizacion(): number {
  const fecha = process.env.FECHA_BUILD;
  const t = fecha ? Date.parse(fecha) : NaN;
  return new Date(Number.isNaN(t) ? Date.now() : t).getFullYear();
}

const TITULO = "Charlie's Pizzas — Pizza de barrio en Tarapoto";
const DESCRIPCION =
  "Charlie's Pizzas: pizza de barrio horneada al momento en Tarapoto desde 2006. Pide delivery o visita nuestros locales.";

export const metadata: Metadata = {
  metadataBase: new URL(URL_SITIO),
  title: { default: TITULO, template: "%s | Charlie's Pizzas" },
  description: DESCRIPCION,
  openGraph: {
    type: "website",
    locale: "es_PE",
    siteName: "Charlie's Pizzas",
    title: TITULO,
    description: DESCRIPCION,
    url: URL_SITIO,
  },
  twitter: {
    card: "summary_large_image",
    title: TITULO,
    description: DESCRIPCION,
  },
};

type Contenido = {
  marca: { nombre: string };
  contenido: {
    contacto?: {
      whatsapp?: string;
      email?: string;
      instagram?: string;
      facebook?: string;
      tiktok?: string;
    };
    pie?: { texto?: string };
  };
};

const NAV = [
  { href: "/carta", etiqueta: "Carta" },
  { href: "/locales", etiqueta: "Locales" },
  { href: "/nosotros", etiqueta: "Nosotros" },
  { href: "/trabaja-con-nosotros", etiqueta: "Trabaja con nosotros" },
];

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [datos, sesion] = await Promise.all([
    apiFetch<Contenido>("/api/v1/storefront/publico/contenido"),
    obtenerSesion(),
  ]);
  const contacto = datos?.contenido?.contacto;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Restaurant",
    name: "Charlie's Pizzas",
    url: URL_SITIO,
    image: `${URL_SITIO}/marcas/logo-vertical.png`,
    servesCuisine: "Pizza",
    priceRange: "S/",
    ...(contacto?.whatsapp ? { telephone: contacto.whatsapp } : {}),
    ...(contacto
      ? {
          sameAs: [
            contacto.instagram && `https://instagram.com/${contacto.instagram}`,
            contacto.facebook && `https://facebook.com/${contacto.facebook}`,
            contacto.tiktok && `https://tiktok.com/@${contacto.tiktok}`,
          ].filter(Boolean),
        }
      : {}),
  };

  return (
    <html lang="es" className={`${tusker.variable} ${isidora.variable}`}>
      {/* Columna de alto mínimo con el `<main>` elástico: es lo que mantiene
          el pie pegado abajo en una página corta (un carrito vacío, un 404)
          en vez de dejarlo flotando a media pantalla. `dvh` y no `vh` por la
          barra del navegador del celular, que cambia de alto al hacer scroll. */}
      <body className="flex min-h-dvh flex-col">
        {/* Restaurant, no LocalBusiness por sucursal: cada local con su
            dirección y horario vive en el JSON-LD de `/locales`, no acá —
            este es el de la marca en general, en cada página. */}
        <script
          type="application/ld+json"
           
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <RevelarObservador />
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b-4 border-negro bg-crema px-4 py-3 sm:px-8">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/marcas/logo-horizontal.svg"
              alt="Charlie's Pizzas"
              width={2265}
              height={192}
              priority
              className="h-5 w-auto sm:h-6"
            />
          </Link>
          <nav className="flex flex-wrap items-center gap-4 text-sm font-bold uppercase">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className="hover:text-verde">
                {n.etiqueta}
              </Link>
            ))}
            <Link href={sesion ? "/cuenta" : "/cuenta/ingresar"} className="hover:text-verde">
              {sesion ? "Mi cuenta" : "Ingresar"}
            </Link>
            <CarritoBadge />
          </nav>
        </header>

        {/* La clave de Maps la lee el proceso de Next y baja por contexto: un
            componente cliente no puede tocar `process.env`, y así el campo de
            dirección del checkout la encuentra sin que cada página se la pase. */}
        <main className="flex-1">
          <ProveedorConfigMapas config={configMapas()}>{children}</ProveedorConfigMapas>
        </main>

        <footer className="mt-12 border-t-4 border-negro bg-negro px-4 py-8 text-sm text-crema sm:px-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <Image
                src="/marcas/logo-horizontal-crema.svg"
                alt="Charlie's Pizzas"
                width={2265}
                height={192}
                className="h-5 w-auto"
              />
              <p className="mt-1 max-w-md text-crema/80">
                {datos?.contenido?.pie?.texto ??
                  "Una marca de Grupo Majambo. Pizza de barrio en Tarapoto."}
              </p>
            </div>
            {contacto && (
              <div className="flex flex-col gap-1 text-crema/90">
                {contacto.whatsapp && <span>WhatsApp: {contacto.whatsapp}</span>}
                {contacto.email && <span>{contacto.email}</span>}
                <div className="flex gap-3">
                  {contacto.instagram && (
                    <a
                      href={`https://instagram.com/${contacto.instagram}`}
                      className="hover:text-verde-hover"
                    >
                      Instagram
                    </a>
                  )}
                  {contacto.facebook && (
                    <a
                      href={`https://facebook.com/${contacto.facebook}`}
                      className="hover:text-verde-hover"
                    >
                      Facebook
                    </a>
                  )}
                  {contacto.tiktok && (
                    <a
                      href={`https://tiktok.com/@${contacto.tiktok}`}
                      className="hover:text-verde-hover"
                    >
                      TikTok
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="mx-auto mt-6 flex max-w-5xl flex-col gap-1 border-t border-crema/20 pt-4 text-xs text-crema/70 sm:flex-row sm:justify-between">
            <span>© {anioDeActualizacion()} Charlie&apos;s Pizzas — Grupo Majambo</span>
            <span>
              Hecho por <strong className="text-crema">TAG Digitales</strong>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
