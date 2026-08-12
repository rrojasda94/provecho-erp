import { Skeleton } from "@/components/ui/skeleton";

/**
 * Lo que se ve mientras una pantalla del ERP resuelve sus datos en el
 * servidor. Es el archivo que cada `<modulo>/loading.tsx` re-exporta.
 *
 * Sin `loading.tsx`, Next espera a que el `page.tsx` termine y recién ahí
 * pinta: el clic en el sidebar no acusa recibo y la sensación es que la
 * aplicación se colgó. Con él, el shell responde de inmediato y lo único que
 * llega tarde es el contenido — que es la verdad.
 *
 * La silueta imita la pantalla real (título, barra de acciones, tabla) en vez
 * de un spinner centrado: un rectángulo donde va a ir la tabla prepara la
 * vista; un spinner solo informa que hay que esperar.
 */
export function EsqueletoPantalla({ filas = 6 }: { filas?: number }) {
  return (
    <div aria-busy aria-label="Cargando">
      <div className="mb-4 flex items-center justify-between gap-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-8 w-32" />
      </div>
      <Skeleton className="mb-3 h-8 w-64" />
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <Skeleton className="h-9 w-full rounded-none" />
        {Array.from({ length: filas }, (_, i) => (
          <div key={i} className="flex gap-4 border-t border-border px-3 py-3">
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-1/6" />
            <Skeleton className="ml-auto h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}
