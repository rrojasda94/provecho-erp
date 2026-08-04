import type { Metadata } from "next";
import { Anton, Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

// Los nombres de variable NO coinciden con los tokens de Tailwind
// (`--font-heading`/`--font-body`) a propósito: si coincidieran, el token se
// referenciaría a sí mismo en `@theme` y la fuente nunca cargaría.
const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--fuente-titulo" });
const inter = Inter({ subsets: ["latin"], variable: "--fuente-texto" });

export const metadata: Metadata = {
    title: "Provecho ERP",
    description: "ERP modular para grupo de restaurantes",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="es" className={`${anton.variable} ${inter.variable}`}>
            <body>
                {children}
                {/* Avisos flotantes (guardado, alertas de cocina). Vive en el
                    layout raíz para que cualquier pantalla pueda emitirlos. */}
                <Toaster richColors closeButton />
            </body>
        </html>
    );
}
