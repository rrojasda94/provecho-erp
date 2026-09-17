/** Configuración de Google Maps leída del entorno del proceso de Next.
 * Copia recortada de `frontend/lib/mapas.ts`: acá no hay campo de
 * dirección ni autocompletado, solo el mapa de locales con marcadores. */
export function configMapas() {
  return {
    apiKey: process.env.GOOGLE_MAPS_BROWSER_KEY ?? "",
    mapId: process.env.GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
  };
}
