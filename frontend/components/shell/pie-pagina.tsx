import pkg from "@/package.json";

/** Pie de página del layout raíz: se ve en toda pantalla —back office, PDV,
 * KDS, login— porque vive en `app/layout.tsx`, no en el shell de ninguna de
 * ellas.
 *
 * `fixed` y no en el flujo normal: el login (`.login-page`, `globals.css`),
 * el PDV y el KDS reclaman la pantalla completa para sí solos
 * (`min-height: 100vh`), así que un pie que empuja contenido quedaría
 * siempre debajo del borde — visible solo scrolleando, que es exactamente lo
 * que "siempre visible" pedía evitar. Angosto (texto `xs`, `py-1`) para que
 * lo que tape en el borde inferior sea mínimo.
 *
 * La versión sale de `package.json` y no de una llamada a la API: es la del
 * frontend que de verdad se sirvió, no la del backend con el que le tocó
 * hablar en ese momento — y `test_repo_coherencia.py` ya obliga a que las dos
 * no se separen (`cortar_version.py` las sube juntas). */
export function PiePagina() {
  return (
    <footer className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 py-1 text-center text-xs text-muted-foreground print:hidden">
      Provecho ERP · v{pkg.version}
    </footer>
  );
}
