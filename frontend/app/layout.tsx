import type { Metadata } from "next";
import { Anton, Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { obtenerPreferencias } from "@/lib/sesion";

// Los nombres de variable NO coinciden con los tokens de Tailwind
// (`--font-heading`/`--font-body`) a propósito: si coincidieran, el token se
// referenciaría a sí mismo en `@theme` y la fuente nunca cargaría.

// Texto y títulos, una sola familia. Archivo es variable en peso Y en ancho:
// el contraste entre un título y un párrafo lo dan el ancho condensado y el
// peso, no una segunda grotesca que se le parece. En un ERP en español, donde
// las etiquetas son largas ("Órdenes de compra pendientes de aprobación"),
// condensar es además lo que hace que quepan sin abreviar.
const archivo = Archivo({
    subsets: ["latin"],
    axes: ["wdth"],
    variable: "--fuente-texto",
});

// Cifras: importes, cantidades, códigos internos, IDs. Monoespaciada para que
// una columna de dinero se lea de arriba abajo sin que los dígitos bailen.
const plexMono = IBM_Plex_Mono({
    weight: ["400", "500", "600"],
    subsets: ["latin"],
    variable: "--fuente-cifra",
});

// Anton queda solo para el logotipo. Era la fuente de TODOS los títulos, en
// itálica y versales — la voz de la carta de Charlie's aplicada a pantallas
// de trabajo. Ahora firma donde corresponde y no se mete en la lectura.
const anton = Anton({ weight: "400", subsets: ["latin"], variable: "--fuente-logo" });

export const metadata: Metadata = {
    title: "Provecho ERP",
    description: "ERP modular para grupo de restaurantes",
};

// `data-escala` y `data-paleta` van en `<html>` y no en un contenedor más
// adentro: `--font-scale` multiplica el `font-size` de la raíz, que es lo que
// hace que TODO lo dimensionado en `rem` escale junto. La clase `dark` va en
// el mismo lugar porque es la que activa la variante `dark:` de Tailwind.
const ESCALA = {
    estandar: undefined,
    grande: "grande",
    muy_grande: "muy-grande",
    maximo: "maximo",
} as const;

export default async function RootLayout({ children }: { children: React.ReactNode }) {
    const prefs = await obtenerPreferencias();

    return (
        <html
            lang="es"
            className={`${archivo.variable} ${plexMono.variable} ${anton.variable} ${
                prefs.preferencia_tema === "oscuro" ? "dark" : ""
            }`}
            data-escala={ESCALA[prefs.preferencia_tamano_fuente]}
            data-paleta={
                prefs.preferencia_paleta === "alto_contraste" ? "alto-contraste" : undefined
            }
        >
            <body>
                {/* Un solo proveedor de tooltips para todo el ERP: con
                    `delay=0` por instancia, pasar el mouse por una fila de
                    íconos dispararía y cancelaría cinco temporizadores. El
                    proveedor los coordina — el primero espera, los
                    siguientes abren al instante. */}
                <TooltipProvider delay={350}>{children}</TooltipProvider>
                {/* Avisos flotantes (guardado, alertas de cocina). Vive en el
                    layout raíz para que cualquier pantalla pueda emitirlos. */}
                <Toaster richColors closeButton />
            </body>
        </html>
    );
}
