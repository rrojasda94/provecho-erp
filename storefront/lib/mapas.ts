/** Configuración de Google Maps leída del entorno del proceso de Next.
 *
 * Copia de `frontend/lib/mapas.ts`. No es `NEXT_PUBLIC_*` a propósito: esa
 * familia se hornea en el build, y así la clave se cambia reiniciando el
 * contenedor en vez de reconstruyendo la imagen. Un Client Component no puede
 * leer `process.env`, por eso baja por contexto
 * (`components/direccion/config-mapas`) desde el layout. */
export function configMapas() {
  return {
    apiKey: process.env.GOOGLE_MAPS_BROWSER_KEY ?? "",
    mapId: process.env.GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
    // Sesga el autocompletado a Perú: sin esto, "Jr. Lima" trae medio mundo.
    pais: process.env.GOOGLE_MAPS_PAIS || "pe",
  };
}
