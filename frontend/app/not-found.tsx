import { ChevronLeft } from "lucide-react";
import Link from "next/link";

/**
 * Página de ruta inexistente. Hasta ahora no había ninguna y el 404 lo
 * resolvía la pantalla por defecto de Next: fondo blanco, "404" en inglés y
 * ninguna salida. En un ERP que se usa en tablet detrás de una barra, una
 * pantalla sin botón de vuelta se resuelve apagando y volviendo a entrar.
 *
 * No dice qué ruta falló: el enlace roto suele venir de un marcador viejo o
 * de una URL recortada a mano, y repetirle la ruta a quien la tecleó no le
 * agrega nada. Lo que necesita es la puerta de vuelta.
 */
export default function NoEncontrado() {
  return (
    <main className="mx-auto max-w-md px-6 py-16 text-center">
      <p className="text-lg font-semibold text-secondary">Esta pantalla no existe</p>
      <p className="mt-2 text-gray">
        El enlace puede estar viejo o la dirección mal escrita. Desde el inicio llegas a
        cualquier módulo al que tengas acceso.
      </p>
      <Link
        href="/"
        className="mt-4 inline-flex items-center gap-1 font-medium text-primary hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Volver al inicio
      </Link>
    </main>
  );
}
