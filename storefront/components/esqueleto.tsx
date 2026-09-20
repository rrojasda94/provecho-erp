/**
 * Piezas grises para los `loading.tsx`.
 *
 * Next muestra el `loading.tsx` de una ruta en cuanto arranca la navegación,
 * antes de que el servidor conteste. Sin él la pantalla se queda congelada en
 * la página anterior y el sitio parece roto — que es exactamente lo que pasaba
 * al tocar un producto de la carta.
 *
 * No llevan texto: un "Cargando..." que aparece y desaparece en 200 ms molesta
 * más de lo que informa. `aria-hidden` con un `role="status"` afuera para que
 * el lector de pantalla anuncie una sola vez, no cada bloque.
 */
export function Bloque({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-negro/10 ${className}`} aria-hidden />;
}

export function Esqueleto({ children }: { children: React.ReactNode }) {
  return (
    <div role="status" aria-label="Cargando">
      {children}
    </div>
  );
}

/** Rejilla de tarjetas: la carta y los favoritos de la portada. */
export function TarjetasEsqueleto({ cantidad = 6 }: { cantidad?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: cantidad }, (_, i) => (
        <div key={i} className="overflow-hidden rounded-lg border-2 border-negro/20 bg-white">
          <Bloque className="h-40 w-full rounded-none" />
          <div className="flex flex-col gap-2 p-3">
            <Bloque className="h-4 w-3/4" />
            <Bloque className="h-3 w-full" />
            <Bloque className="h-5 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
