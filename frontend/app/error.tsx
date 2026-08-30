"use client";

import { ChevronLeft, RotateCw } from "lucide-react";
import Link from "next/link";

/**
 * Lo que se ve cuando una pantalla revienta al renderizar.
 *
 * Hasta ahora no había ninguna: un throw en un Server Component —el de
 * `(app)/layout.tsx`, que pide la sesión, es el caso gordo— caía en la
 * pantalla por defecto de Next, que en producción es blanca y sin salida. En
 * una tablet detrás de una barra eso se resuelve apagando el equipo.
 *
 * Vive en `app/` y no en `app/(app)/` a propósito: así también cubre PDV,
 * KDS, asistencia, login y las rutas públicas, que cuelgan directo del layout
 * raíz, y alcanza a los throws del propio layout del back office.
 *
 * El reintento es `reset()` y no `router.refresh()`: es la primitiva del
 * boundary y vuelve a montar el segmento caído. `AvisoFallo` usa `refresh()`
 * porque no es un boundary — es un bloque dentro de una página que sí
 * renderizó.
 *
 * El `digest` se muestra porque en producción Next reemplaza el mensaje del
 * servidor por uno genérico, y es lo único que ata esta pantalla a la línea
 * del log. Un aviso que solo dice "algo falló" obliga a abrir las
 * herramientas de desarrollo, que es justo lo que no se puede pedir en un
 * mostrador.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-md px-6 py-16 text-center">
      <p className="text-lg font-semibold text-secondary">Esta pantalla se cayó</p>
      <p className="mt-2 text-gray">
        No es algo que hayas hecho mal. Reintentar suele alcanzar; si vuelve a pasar,
        pasa el código de abajo a quien lleva el sistema.
      </p>
      <p className="mt-3 font-mono text-xs break-words text-gray">
        {error.message}
        {error.digest ? ` · ${error.digest}` : ""}
      </p>
      <div className="mt-6 flex items-center justify-center gap-4">
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-1 rounded border border-secondary/40 px-3 py-1.5 text-sm font-semibold text-secondary"
        >
          <RotateCw size={16} strokeWidth={2} aria-hidden />
          Reintentar
        </button>
        <Link
          href="/"
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
        >
          <ChevronLeft size={16} strokeWidth={2} aria-hidden />
          Volver al inicio
        </Link>
      </div>
    </main>
  );
}
