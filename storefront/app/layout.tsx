import { Anton, Archivo } from "next/font/google";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";
import { CarritoBadge } from "@/components/carrito-badge";
import { RevelarObservador } from "@/components/revelar-observador";

import "./globals.css";

const anton = Anton({
  subsets: ["latin"],
  weight: "400",
  variable: "--fuente-display-google",
  display: "swap",
});
const archivo = Archivo({
  subsets: ["latin"],
  variable: "--fuente-cuerpo-google",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Charlie's Pizzas — Pizza de barrio en Tarapoto",
    template: "%s | Charlie's Pizzas",
  },
  description:
    "Charlie's Pizzas: pizza de barrio horneada al momento en Tarapoto desde 2006. Pide delivery o visita nuestros locales.",
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

  return (
    <html lang="es" className={`${anton.variable} ${archivo.variable}`}>
      <body>
        <RevelarObservador />
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b-4 border-negro bg-crema px-4 py-3 sm:px-8">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/marcas/logo.png" alt="Charlie's Pizzas" width={140} height={47} priority />
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

        <main>{children}</main>

        <footer className="mt-12 border-t-4 border-negro bg-negro px-4 py-8 text-sm text-crema sm:px-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-display text-lg uppercase">Charlie&apos;s Pizzas</p>
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
        </footer>
      </body>
    </html>
  );
}
